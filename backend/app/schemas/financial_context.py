"""Phase 3.1 Financial Context schemas.

A typed, read-only representation of the authenticated user's financial state.
All monetary values are integer minor units. Optional[int] is used wherever a
dataset is genuinely unavailable so that future AI consumers can distinguish
"known zero" from "not provided".

No LLM logic lives here. This module is pure data/domain schema.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Optional

from pydantic import BaseModel, Field, StrictInt


# ---------------------------------------------------------------------------
# Employment / income
# ---------------------------------------------------------------------------


class EmploymentContext(BaseModel):
    employment_id: Optional[str] = None
    employer_id: Optional[str] = None
    employer_name: Optional[str] = None
    employment_status: Optional[str] = None


class IncomeContext(BaseModel):
    salary_amount_minor: Optional[int] = None
    currency: Optional[str] = None
    pay_period_start: Optional[date] = None
    pay_period_end: Optional[date] = None


# ---------------------------------------------------------------------------
# EWA (authoritative - mirrors calculate_ewa() exactly)
# ---------------------------------------------------------------------------


class EwaContext(BaseModel):
    earned_amount_minor: int
    policy_limit_minor: int
    reserved_amount_minor: int
    paid_amount_minor: int
    available_amount_minor: int
    max_requestable_amount_minor: int

    pay_period_start: Optional[date] = None
    pay_period_end: Optional[date] = None
    calculation_date: Optional[date] = None

    salary_amount_minor: Optional[int] = None

    eligible: bool
    eligibility_reasons: list[str] = Field(default_factory=list)

    minimum_withdrawal_minor: Optional[int] = None
    maximum_withdrawal_minor: Optional[int] = None

    can_request_withdrawal: bool = False
    max_withdrawals_per_period: Optional[int] = None
    withdrawals_this_period: int = 0


# ---------------------------------------------------------------------------
# Withdrawal history
# ---------------------------------------------------------------------------


class RecentWithdrawal(BaseModel):
    id: str
    amount_minor: int
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class WithdrawalHistoryContext(BaseModel):
    available: bool = True

    total_requests: int = 0
    pending_count: int = 0
    approved_count: int = 0
    paid_count: int = 0
    rejected_count: int = 0
    cancelled_count: int = 0

    requested_amount_minor: int = 0
    paid_amount_minor: int = 0

    recent_requests: list[RecentWithdrawal] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Spending / transactions
# ---------------------------------------------------------------------------


class CategoryBreakdown(BaseModel):
    category: str
    amount_minor: int
    transaction_count: int = 0


class SpendingContext(BaseModel):
    available: bool

    total_spending_minor: Optional[int] = None
    transaction_count: int = 0

    essential_spending_minor: Optional[int] = None
    discretionary_spending_minor: Optional[int] = None

    category_breakdown: list[CategoryBreakdown] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------


class BudgetContext(BaseModel):
    available: bool

    total_budget_minor: Optional[int] = None
    spent_minor: Optional[int] = None
    remaining_minor: Optional[int] = None


# ---------------------------------------------------------------------------
# Goals
# ---------------------------------------------------------------------------


class FinancialGoalContext(BaseModel):
    id: str
    title: str
    target_minor: int
    current_minor: int
    status: str
    progress_pct: int


class GoalsContext(BaseModel):
    available: bool

    active_goals_count: Optional[int] = None
    total_target_minor: Optional[int] = None
    total_saved_minor: Optional[int] = None

    goals: list[FinancialGoalContext] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Data quality
# ---------------------------------------------------------------------------


class DataQualityContext(BaseModel):
    has_salary_profile: bool
    has_ewa_policy: bool
    has_transactions: bool
    has_budget: bool
    has_goals: bool

    missing_data: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Top-level FinancialContext
# ---------------------------------------------------------------------------


class FinancialContext(BaseModel):
    user_id: str

    generated_at: Optional[str] = None
    calculation_date: Optional[date] = None

    employment: EmploymentContext = Field(default_factory=EmploymentContext)
    income: IncomeContext = Field(default_factory=IncomeContext)

    ewa: EwaContext

    withdrawal_history: WithdrawalHistoryContext = Field(default_factory=WithdrawalHistoryContext)
    spending: SpendingContext
    budget: BudgetContext
    goals: GoalsContext

    data_quality: DataQualityContext


# ---------------------------------------------------------------------------
# Phase 3.2  Deterministic Withdrawal Analysis
# ---------------------------------------------------------------------------
# Analyzed for an authenticated user given a single hypothetical withdrawal
# amount. The analysis is strictly read-only: it never creates a withdrawal,
# reserves capacity, mutates budgets/goals/transactions, or increments the
# withdrawal count. All monetary values are integer minor units; ratios are
# integer basis points (10000 bps == 100%). No LLM / AI logic here.
# ---------------------------------------------------------------------------


class WithdrawalAnalysisRequest(BaseModel):
    """Input for a withdrawal analysis. Strict positive integer only.

    Rejects 0, negatives, floats, and booleans; no caller-controlled
    user/employee/employer selectors are accepted.
    """

    amount_minor: Annotated[StrictInt, Field(gt=0)]


class Requestability(BaseModel):
    requestable: bool
    blocking_reasons: list[str] = Field(default_factory=list)
    authoritative_eligibility_reasons: list[str] = Field(default_factory=list)


class CurrentState(BaseModel):
    salary_amount_minor: Optional[int] = None
    earned_amount_minor: Optional[int] = None
    policy_limit_minor: Optional[int] = None
    reserved_amount_minor: Optional[int] = None
    paid_amount_minor: Optional[int] = None
    available_amount_minor: Optional[int] = None
    max_requestable_amount_minor: Optional[int] = None


class Impact(BaseModel):
    remaining_available_amount_minor: Optional[int] = None
    remaining_max_requestable_amount_minor: Optional[int] = None
    requested_share_of_earned_bps: Optional[int] = None
    requested_share_of_policy_limit_bps: Optional[int] = None
    exposure_before_minor: Optional[int] = None
    exposure_after_minor: Optional[int] = None
    exposure_share_of_earned_before_bps: Optional[int] = None
    exposure_share_of_earned_after_bps: Optional[int] = None


class WithdrawalFrequency(BaseModel):
    withdrawals_this_period: int = 0
    max_withdrawals_per_period: Optional[int] = None
    remaining_slots_before: Optional[int] = None
    remaining_slots_after: Optional[int] = None


class BudgetImpact(BaseModel):
    available: bool = False
    total_budget_minor: Optional[int] = None
    current_spent_minor: Optional[int] = None
    current_remaining_minor: Optional[int] = None
    withdrawal_share_of_budget_bps: Optional[int] = None


class DataQualityAnalysis(BaseModel):
    has_transactions: bool = False
    has_budget: bool = False
    has_goals: bool = False
    unavailable_analysis: Optional[str] = None


class WithdrawalAnalysis(BaseModel):
    requested_amount_minor: int
    requestability: Requestability
    current_state: CurrentState
    impact: Impact
    withdrawal_frequency: WithdrawalFrequency
    budget_impact: BudgetImpact
    data_quality: DataQualityAnalysis
    snapshot_only: bool = True