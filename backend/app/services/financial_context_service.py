"""Phase 3.1 Financial Context Builder service.

Builds a typed, read-only FinancialContext for the authenticated user.

Authoritative EWA values come exclusively from the Phase 2 EWA engine
(calculate_ewa). No EWA formula is reimplemented here.

All monetary values are integer minor units. Optional[int] is used
wherever a dataset is genuinely unavailable so future AI consumers can
distinguish "known zero" from "not provided".

No LLM calls. No data fabrication.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Budget,
    Employee,
    Employer,
    Employment,
    Goal,
    SalaryProfile,
    Transaction,
    User,
    WageAccessRequest,
)
from app.services.ewa_engine import (
    EWAResult,
    _get_active_employment,
    _get_active_salary_profile,
    _get_ewa_policy,
    calculate_ewa,
)
from app.schemas.financial_context import (
    BudgetContext,
    BudgetImpact,
    CategoryBreakdown,
    CurrentState,
    DataQualityAnalysis,
    DataQualityContext,
    EwaContext,
    EmploymentContext,
    FinancialContext,
    FinancialGoalContext,
    GoalsContext,
    Impact,
    IncomeContext,
    RecentWithdrawal,
    Requestability,
    SpendingContext,
    WithdrawalAnalysis,
    WithdrawalFrequency,
    WithdrawalHistoryContext,
)

RECENT_WITHDRAWALS_LIMIT = 10


async def build_financial_context(
    db: AsyncSession,
    user: User,
    calculation_date: Optional[date] = None,
) -> FinancialContext:
    """Build the authoritative FinancialContext for an authenticated user.

    All EWA values are delegated to calculate_ewa() (Phase 2 engine).
    """
    if calculation_date is None:
        calculation_date = date.today()

    employee = (
        await db.execute(select(Employee).where(Employee.user_id == user.id))
    ).scalar_one_or_none()

    calc = await calculate_ewa(db, user.id, calculation_date)

    employment = None
    salary_profile = None
    employer = None
    if employee is not None:
        employment = await _get_active_employment(db, employee.id, calculation_date)
        if employment is not None:
            salary_profile = await _get_active_salary_profile(
                db, employment.id, calculation_date
            )
            employer = await _get_employer(db, employment)

    ewa = _build_ewa_context(calc)
    withdrawal_history = await _build_withdrawal_history(db, user.id)
    spending = await _build_spending_context(db, user.id)
    budget = await _build_budget_context(db, user.id)
    goals = await _build_goals_context(db, user.id)
    data_quality = _build_data_quality(
        has_salary_profile=salary_profile is not None,
        has_ewa_policy=await _has_ewa_policy(db, employment),
        has_transactions=True,
        has_budget=budget.available,
        has_goals=goals.available,
        missing_data=_build_missing_data(
            salary_profile is not None,
            await _has_ewa_policy(db, employment),
            budget.available,
            goals.available,
        ),
    )

    return FinancialContext(
        user_id=user.id,
        generated_at=datetime.utcnow().isoformat(),
        calculation_date=calculation_date,
        employment=_build_employment_context(employment) if employment else EmploymentContext(),
        income=_build_income_context(salary_profile, calc),
        ewa=ewa,
        withdrawal_history=withdrawal_history,
        spending=spending,
        budget=budget,
        goals=goals,
        data_quality=data_quality,
    )


async def _get_employer(db: AsyncSession, employment: Employment) -> Optional[Employer]:
    result = await db.execute(select(Employer).where(Employer.id == employment.employer_id))
    return result.scalar_one_or_none()


async def _has_ewa_policy(db: AsyncSession, employment: Optional[Employment]) -> bool:
    if employment is None:
        return False
    policy = await _get_ewa_policy(db, employment.employer_id)
    return policy is not None


def _build_ewa_context(calc: EWAResult) -> EwaContext:
    return EwaContext(
        earned_amount_minor=calc.earned_amount_minor,
        policy_limit_minor=calc.policy_limit_minor,
        reserved_amount_minor=calc.reserved_amount_minor,
        paid_amount_minor=calc.paid_amount_minor,
        available_amount_minor=calc.available_amount_minor,
        max_requestable_amount_minor=calc.max_requestable_amount_minor,
        pay_period_start=calc.pay_period_start,
        pay_period_end=calc.pay_period_end,
        calculation_date=calc.calculation_date,
        salary_amount_minor=calc.salary_amount_minor,
        eligible=calc.eligible,
        eligibility_reasons=list(calc.eligibility_reasons),
        minimum_withdrawal_minor=calc.minimum_withdrawal_minor,
        maximum_withdrawal_minor=calc.maximum_withdrawal_minor,
        can_request_withdrawal=calc.can_request_withdrawal,
        max_withdrawals_per_period=calc.max_withdrawals_per_period,
        withdrawals_this_period=calc.withdrawals_this_period,
    )


def _build_income_context(
    salary_profile: Optional[SalaryProfile], calc: EWAResult
) -> IncomeContext:
    return IncomeContext(
        salary_amount_minor=(
            salary_profile.monthly_salary_amount_minor
            if salary_profile is not None
            else None
        ),
        currency=salary_profile.currency if salary_profile else None,
        pay_period_start=calc.pay_period_start,
        pay_period_end=calc.pay_period_end,
    )


def _build_employment_context(
    employment: Optional[Employment],
) -> EmploymentContext:
    if employment is None:
        return EmploymentContext()
    return EmploymentContext(
        employment_id=employment.id,
        employer_id=employment.employer_id,
        employer_name=(
            employment.employer.display_name or employment.employer.legal_name
            if employment.employer
            else None
        ),
        employment_status=employment.status,
    )


async def _build_withdrawal_history(
    db: AsyncSession, user_id: str
) -> WithdrawalHistoryContext:
    agg = (
        await db.execute(
            select(
                func.count(WageAccessRequest.id).label("total_requests"),
                func.sum(case((WageAccessRequest.status == "pending", 1), else_=0)).label("pending_count"),
                func.sum(case((WageAccessRequest.status == "approved", 1), else_=0)).label("approved_count"),
                func.sum(case((WageAccessRequest.status == "paid", 1), else_=0)).label("paid_count"),
                func.sum(case((WageAccessRequest.status == "rejected", 1), else_=0)).label("rejected_count"),
                func.sum(case((WageAccessRequest.status == "cancelled", 1), else_=0)).label("cancelled_count"),
                func.coalesce(func.sum(WageAccessRequest.amount_minor), 0).label("requested_amount_minor"),
                func.coalesce(
                    func.sum(case((WageAccessRequest.status == "paid", WageAccessRequest.amount_minor), else_=0)),
                    0,
                ).label("paid_amount_minor"),
            ).where(WageAccessRequest.user_id == user_id)
        )
    ).one()

    recent = (
        await db.execute(
            select(
                WageAccessRequest.id,
                WageAccessRequest.amount_minor,
                WageAccessRequest.status,
                WageAccessRequest.created_at,
                WageAccessRequest.updated_at,
            )
            .where(WageAccessRequest.user_id == user_id)
            .order_by(WageAccessRequest.created_at.desc())
            .limit(RECENT_WITHDRAWALS_LIMIT)
        )
    ).all()

    recent_requests = [
        RecentWithdrawal(
            id=r.id,
            amount_minor=r.amount_minor,
            status=r.status,
            created_at=r.created_at.isoformat() if r.created_at else None,
            updated_at=r.updated_at.isoformat() if r.updated_at else None,
        )
        for r in recent
    ]

    return WithdrawalHistoryContext(
        total_requests=agg.total_requests or 0,
        pending_count=agg.pending_count or 0,
        approved_count=agg.approved_count or 0,
        paid_count=agg.paid_count or 0,
        rejected_count=agg.rejected_count or 0,
        cancelled_count=agg.cancelled_count or 0,
        requested_amount_minor=agg.requested_amount_minor or 0,
        paid_amount_minor=agg.paid_amount_minor or 0,
        recent_requests=recent_requests,
    )


async def _build_spending_context(db: AsyncSession, user_id: str) -> SpendingContext:
    rows = (
        await db.execute(
            select(
                Transaction.category,
                func.sum(Transaction.amount_minor).label("amount_minor"),
                func.count(Transaction.id).label("transaction_count"),
            )
            .where(Transaction.user_id == user_id, Transaction.type == "expense")
            .group_by(Transaction.category)
        )
    ).all()

    total_spending = sum(r.amount_minor for r in rows)
    transaction_count = sum(r.transaction_count for r in rows)
    category_breakdown = [
        CategoryBreakdown(
            category=r.category or "",
            amount_minor=r.amount_minor,
            transaction_count=r.transaction_count,
        )
        for r in rows
    ]

    return SpendingContext(
        available=True,
        total_spending_minor=total_spending,
        transaction_count=transaction_count,
        essential_spending_minor=None,
        discretionary_spending_minor=None,
        category_breakdown=category_breakdown,
    )


async def _build_budget_context(db: AsyncSession, user_id: str) -> BudgetContext:
    rows = (
        await db.execute(select(Budget).where(Budget.user_id == user_id))
    ).scalars().all()

    if not rows:
        return BudgetContext(available=False)

    total_budget = sum(r.limit_minor for r in rows)
    spent = sum(r.spent_minor for r in rows)

    return BudgetContext(
        available=True,
        total_budget_minor=total_budget,
        spent_minor=spent,
        remaining_minor=total_budget - spent,
    )


async def _build_goals_context(db: AsyncSession, user_id: str) -> GoalsContext:
    rows = (
        await db.execute(
            select(
                Goal.id,
                Goal.title,
                Goal.target_minor,
                Goal.current_minor,
                Goal.status,
                Goal.progress_pct,
            )
            .where(Goal.user_id == user_id, Goal.status == "active")
        )
    ).all()

    if not rows:
        return GoalsContext(available=False)

    goals = [
        FinancialGoalContext(
            id=r.id,
            title=r.title,
            target_minor=r.target_minor,
            current_minor=r.current_minor,
            status=r.status,
            progress_pct=r.progress_pct,
        )
        for r in rows
    ]

    return GoalsContext(
        available=True,
        active_goals_count=len(goals),
        total_target_minor=sum(g.target_minor for g in goals),
        total_saved_minor=sum(g.current_minor for g in goals),
        goals=goals,
    )


def _build_data_quality(
    has_salary_profile: bool,
    has_ewa_policy: bool,
    has_transactions: bool,
    has_budget: bool,
    has_goals: bool,
    missing_data: list[str],
) -> DataQualityContext:
    return DataQualityContext(
        has_salary_profile=has_salary_profile,
        has_ewa_policy=has_ewa_policy,
        has_transactions=has_transactions,
        has_budget=has_budget,
        has_goals=has_goals,
        missing_data=missing_data,
    )


def _build_missing_data(
    has_salary_profile: bool,
    has_ewa_policy: bool,
    has_budget: bool,
    has_goals: bool,
) -> list[str]:
    missing = []
    if not has_salary_profile:
        missing.append("salary_profile")
    if not has_ewa_policy:
        missing.append("ewa_policy")
    if not has_budget:
        missing.append("budget")
    if not has_goals:
        missing.append("financial_goals")
    return missing


# ---------------------------------------------------------------------------
# Phase 3.2  Deterministic Withdrawal Analysis Engine
# ---------------------------------------------------------------------------
# Pure, read-only analysis of a single hypothetical withdrawal amount against
# the authoritative FinancialContext. No state is mutated; calling the analysis
# twice leaves capacity unchanged. Actual withdrawal creation remains the sole
# responsibility of POST /ewa/request.
# ---------------------------------------------------------------------------

# Deterministic, machine-readable blocking reason codes for Phase 3.2.
WITHDRAWAL_BLOCK_EWA_NOT_ELIGIBLE = "EWA_NOT_ELIGIBLE"
WITHDRAWAL_BLOCK_WITHDRAWAL_NOT_ALLOWED = "WITHDRAWAL_NOT_ALLOWED"
WITHDRAWAL_BLOCK_AMOUNT_BELOW_MINIMUM = "AMOUNT_BELOW_MINIMUM"
WITHDRAWAL_BLOCK_AMOUNT_EXCEEDS_MAX_REQUESTABLE = "AMOUNT_EXCEEDS_MAX_REQUESTABLE"
WITHDRAWAL_BLOCK_WITHDRAWAL_LIMIT_REACHED = "WITHDRAWAL_LIMIT_REACHED"


def _bps(numerator: int | None, denominator: int | None) -> Optional[int]:
    """Integer basis points: (numerator * 10000) // denominator.

    Returns None when the denominator is unknown or non-positive, or when
    either operand is None. No floating point is ever produced.
    """
    if numerator is None or denominator is None:
        return None
    if denominator <= 0:
        return None
    return (numerator * 10000) // denominator


def _remaining_slots_before(
    max_per_period: Optional[int], count: int
) -> Optional[int]:
    if max_per_period is None:
        return None
    return max(0, max_per_period - count)


def analyze_withdrawal_from_context(
    ctx: FinancialContext, amount_minor: int
) -> WithdrawalAnalysis:
    """Deterministic, read-only withdrawal analysis.

    All current-state values are taken directly from the authoritative
    FinancialContext (which itself delegates EWA to calculate_ewa). This
    function performs no database writes and never creates or mutates a
    WageAccessRequest, Budget, Goal, or Transaction.
    """
    ewa = ctx.ewa

    authoritative_reasons = list(ewa.eligibility_reasons)

    max_per_period = ewa.max_withdrawals_per_period
    count = ewa.withdrawals_this_period
    limit_reached = max_per_period is not None and count >= max_per_period
    engine_limit_exceeded = bool(
        ewa.eligibility_reasons
        and "MAX_WITHDRAWALS_EXCEEDED" in ewa.eligibility_reasons
    )

    blocking: list[str] = []
    if not ewa.eligible and not limit_reached:
        blocking.append(WITHDRAWAL_BLOCK_EWA_NOT_ELIGIBLE)
    if limit_reached or engine_limit_exceeded:
        blocking.append(WITHDRAWAL_BLOCK_WITHDRAWAL_LIMIT_REACHED)
    if (
        ewa.eligible
        and not limit_reached
        and not ewa.can_request_withdrawal
    ):
        blocking.append(WITHDRAWAL_BLOCK_WITHDRAWAL_NOT_ALLOWED)

    amount_gated = (
        ewa.eligible
        and not limit_reached
        and ewa.can_request_withdrawal
    )
    if amount_gated:
        if (
            ewa.minimum_withdrawal_minor is not None
            and amount_minor < ewa.minimum_withdrawal_minor
        ):
            blocking.append(WITHDRAWAL_BLOCK_AMOUNT_BELOW_MINIMUM)
        if amount_minor > ewa.max_requestable_amount_minor:
            blocking.append(WITHDRAWAL_BLOCK_AMOUNT_EXCEEDS_MAX_REQUESTABLE)

    requestable = len(blocking) == 0

    current_state = CurrentState(
        salary_amount_minor=ewa.salary_amount_minor,
        earned_amount_minor=ewa.earned_amount_minor,
        policy_limit_minor=ewa.policy_limit_minor,
        reserved_amount_minor=ewa.reserved_amount_minor,
        paid_amount_minor=ewa.paid_amount_minor,
        available_amount_minor=ewa.available_amount_minor,
        max_requestable_amount_minor=ewa.max_requestable_amount_minor,
    )

    exposure_before = ewa.reserved_amount_minor + ewa.paid_amount_minor

    if requestable:
        remaining_available = max(0, ewa.available_amount_minor - amount_minor)
        remaining_max_requestable = max(
            0, ewa.max_requestable_amount_minor - amount_minor
        )
        exposure_after = exposure_before + amount_minor
        slots_before = _remaining_slots_before(max_per_period, count)
        if max_per_period is not None and slots_before is not None:
            remaining_slots_after = max(0, slots_before - 1)
        else:
            remaining_slots_after = None
    else:
        remaining_available = None
        remaining_max_requestable = None
        exposure_after = None
        remaining_slots_after = None

    slots_before = _remaining_slots_before(max_per_period, count)

    impact = Impact(
        remaining_available_amount_minor=remaining_available,
        remaining_max_requestable_amount_minor=remaining_max_requestable,
        requested_share_of_earned_bps=_bps(amount_minor, ewa.earned_amount_minor),
        requested_share_of_policy_limit_bps=_bps(
            amount_minor, ewa.policy_limit_minor
        ),
        exposure_before_minor=exposure_before,
        exposure_after_minor=exposure_after,
        exposure_share_of_earned_before_bps=_bps(exposure_before, ewa.earned_amount_minor),
        exposure_share_of_earned_after_bps=_bps(exposure_after, ewa.earned_amount_minor),
    )

    withdrawal_frequency = WithdrawalFrequency(
        withdrawals_this_period=ewa.withdrawals_this_period,
        max_withdrawals_per_period=ewa.max_withdrawals_per_period,
        remaining_slots_before=slots_before,
        remaining_slots_after=remaining_slots_after,
    )

    budget = ctx.budget
    if budget.available:
        budget_impact = BudgetImpact(
            available=True,
            total_budget_minor=budget.total_budget_minor,
            current_spent_minor=budget.spent_minor,
            current_remaining_minor=budget.remaining_minor,
            withdrawal_share_of_budget_bps=_bps(
                amount_minor, budget.total_budget_minor
            ),
        )
    else:
        budget_impact = BudgetImpact(available=False)

    data_quality = DataQualityAnalysis(
        has_transactions=ctx.data_quality.has_transactions,
        has_budget=ctx.data_quality.has_budget,
        has_goals=ctx.data_quality.has_goals,
        unavailable_analysis=None,
    )

    return WithdrawalAnalysis(
        requested_amount_minor=amount_minor,
        requestability=Requestability(
            requestable=requestable,
            blocking_reasons=blocking,
            authoritative_eligibility_reasons=authoritative_reasons,
        ),
        current_state=current_state,
        impact=impact,
        withdrawal_frequency=withdrawal_frequency,
        budget_impact=budget_impact,
        data_quality=data_quality,
        snapshot_only=True,
    )


async def analyze_withdrawal(
    db: AsyncSession,
    user: User,
    amount_minor: int,
    calculation_date: Optional[date] = None,
) -> WithdrawalAnalysis:
    """Build the authoritative FinancialContext for the authenticated user and
    run the deterministic withdrawal analysis on it.

    Read-only: no rows are written or mutated. Identity comes exclusively
    from the authenticated user.
    """
    ctx = await build_financial_context(db, user, calculation_date)
    return analyze_withdrawal_from_context(ctx, amount_minor)