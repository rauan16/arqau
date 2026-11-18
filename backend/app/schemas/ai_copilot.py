"""Phase 3.4 AI Financial Copilot schemas.

Trust boundary:

- `CopilotContent` is the AI-owned output. It contains NO authoritative
  financial fields (earned amount, available amount, policy limit, max
  requestable, accessed/reserved amounts, eligibility, withdrawal counts,
  budget totals, remaining budget). The LLM is never asked to calculate,
  determine, or author financial state; only the `json_schema` of
  `CopilotContent` is sent to the provider. `extra="forbid"` means the model
  cannot smuggle in fields the backend has not validated.

- `CopilotAnswer` wraps `CopilotContent` with a SERVER-OWNED disclaimer and
  `CopilotMetadata`. Neither the disclaimer nor the metadata is ever taken
  from provider output: the disclaimer is a server constant and the metadata
  reflects whether the provider actually produced the content or a
  deterministic fallback was used.

- `AuthoritativeCopilotFacts` is assembled server-side from the Phase 3.1
  `FinancialContext` (and, when the question is withdrawal-specific, the
  Phase 3.2 `WithdrawalAnalysis`). Every monetary value is an integer number
  of minor units; `Optional[int]` distinguishes a genuine zero from data that
  was never available.

- `CopilotResponse` is the deterministic envelope returned by POST /ai/chat.
  The legacy `response` and `disclaimer` fields are preserved for API
  compatibility; the structured fields are additive.

No LLM logic lives in this module. This is pure data/domain schema.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.financial_context import WithdrawalAnalysis


class CopilotFact(BaseModel):
    """A single explanatory fact. Prose only; no numerical authority."""

    model_config = ConfigDict(extra="forbid")
    code: str
    text: str


class CopilotMetadata(BaseModel):
    """Server-owned attribution. The provider never sets this."""

    model_config = ConfigDict(extra="forbid")
    generated: bool
    fallback_used: bool
    provider: Optional[str] = None
    model: Optional[str] = None
    fallback_reason: Optional[str] = None


class CopilotContent(BaseModel):
    """The AI-owned, schema-validated output. No numerical authority lives here.

    Note there is no `disclaimer` field: the disclaimer is server-owned, so a
    model can neither supply nor suppress it.
    """

    model_config = ConfigDict(extra="forbid")

    response: str
    key_facts: list[CopilotFact] = Field(default_factory=list)
    data_limitations: list[str] = Field(default_factory=list)
    suggested_questions: list[str] = Field(default_factory=list)


class CopilotAnswer(BaseModel):
    """Validated explanation: AI content plus server-owned disclaimer/metadata."""

    model_config = ConfigDict(extra="forbid")

    response: str
    key_facts: list[CopilotFact] = Field(default_factory=list)
    data_limitations: list[str] = Field(default_factory=list)
    suggested_questions: list[str] = Field(default_factory=list)
    disclaimer: str
    ai_metadata: CopilotMetadata


class SpendingCategoryFact(BaseModel):
    """Server-aggregated spending category. Aggregates only — never raw rows."""

    model_config = ConfigDict(extra="forbid")
    category: str
    amount_minor: int
    transaction_count: int


class AuthoritativeCopilotFacts(BaseModel):
    """Server-assembled authoritative facts.

    Every value here is copied from the Phase 3.1 `FinancialContext` (whose EWA
    values are delegated to the Phase 2 engine) or from the Phase 3.2
    `WithdrawalAnalysis`. Nothing in this model is produced, inferred, or
    restated by the LLM.

    There is intentionally NO `recommended_amount_minor` field: availability is
    never a recommendation. `availability_note` states that server-side.
    """

    model_config = ConfigDict(extra="forbid")

    calculation_date: Optional[str] = None
    pay_period_start: Optional[str] = None
    pay_period_end: Optional[str] = None

    salary_amount_minor: Optional[int] = None
    currency: Optional[str] = None

    earned_amount_minor: Optional[int] = None
    policy_limit_minor: Optional[int] = None
    reserved_amount_minor: Optional[int] = None
    paid_amount_minor: Optional[int] = None
    available_amount_minor: Optional[int] = None
    max_requestable_amount_minor: Optional[int] = None
    minimum_withdrawal_minor: Optional[int] = None
    maximum_withdrawal_minor: Optional[int] = None

    # Reserve tracking (period surplus vs target, not actual savings)
    reserve_target_minor: Optional[int] = None
    period_net_surplus_minor: Optional[int] = None
    reserve_shortfall_minor: Optional[int] = None
    reserve_progress_ratio: Optional[float] = None
    upcoming_bills_total_minor: Optional[int] = None
    upcoming_bills_unpaid_minor: Optional[int] = None

    eligible: Optional[bool] = None
    eligibility_reasons: list[str] = Field(default_factory=list)
    can_request_withdrawal: Optional[bool] = None

    withdrawals_this_period: Optional[int] = None
    max_withdrawals_per_period: Optional[int] = None

    total_withdrawal_requests: Optional[int] = None
    pending_withdrawal_count: Optional[int] = None
    approved_withdrawal_count: Optional[int] = None
    paid_withdrawal_count: Optional[int] = None
    paid_withdrawal_amount_minor: Optional[int] = None

    spending_available: Optional[bool] = None
    total_spending_minor: Optional[int] = None
    transaction_count: Optional[int] = None
    top_spending_categories: list[SpendingCategoryFact] = Field(default_factory=list)

    budget_available: Optional[bool] = None
    budget_total_minor: Optional[int] = None
    budget_spent_minor: Optional[int] = None
    budget_remaining_minor: Optional[int] = None

    goals_available: Optional[bool] = None
    active_goals_count: Optional[int] = None
    total_goal_target_minor: Optional[int] = None
    total_goal_saved_minor: Optional[int] = None

    has_salary_profile: Optional[bool] = None
    has_ewa_policy: Optional[bool] = None
    has_transactions: Optional[bool] = None
    has_budget: Optional[bool] = None
    has_goals: Optional[bool] = None
    missing_data: list[str] = Field(default_factory=list)

    availability_note: str


class CopilotResponse(BaseModel):
    """Deterministic envelope returned by POST /ai/chat (read-only).

    `response` and `disclaimer` preserve the legacy /ai/chat contract. The
    remaining fields are additive and authoritative/server-owned.
    """

    model_config = ConfigDict(extra="forbid")

    response: str
    key_facts: list[CopilotFact] = Field(default_factory=list)
    data_limitations: list[str] = Field(default_factory=list)
    suggested_questions: list[str] = Field(default_factory=list)
    disclaimer: str

    authoritative_facts: AuthoritativeCopilotFacts

    withdrawal_analysis: Optional[WithdrawalAnalysis] = None

    product_search_results: Optional[list["ProductSearchResultItem"]] = None

    conversation_id: Optional[str] = None
    conversation_persisted: bool = False

    ai_metadata: CopilotMetadata

    read_only: bool = True
    snapshot_only: bool = True


class ProductSearchResultItem(BaseModel):
    """Product search result item returned in AI chat response."""
    source: str
    product_id: str
    title: str
    price_minor: int
    currency: str
    seller: Optional[str] = None
    url: Optional[str] = None
    availability: Optional[str] = None
    delivery_info: Optional[str] = None