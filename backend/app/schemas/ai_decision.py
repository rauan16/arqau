"""Phase 3.3 Structured AI Decision schemas.

Trust boundary:

- `DecisionContent` is the AI-owned output. It contains NO authoritative
  financial fields (requestable, blocking reasons, balances, limits,
  withdrawal counts, budget totals). The LLM is never asked to calculate or
  decide financial state. Only the `json_schema` of `DecisionContent` is sent
  to the provider.

- `StructuredDecision` wraps `DecisionContent` with `ai_metadata`, which is
  SERVER-OWNED (reflecting whether the LLM actually produced the content or a
  deterministic fallback was used). The provider is never trusted to set it.

- `WithdrawalDecisionResponse` is the deterministic envelope: authoritative
  fields are copied directly from Phase 3.2 `WithdrawalAnalysis` and are never
  derived from, or overwritten by, LLM output.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DecisionFact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    text: str


class DecisionConsideration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    text: str


class DecisionOption(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    text: str


class AIMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    generated: bool
    fallback_used: bool
    provider: Optional[str] = None
    model: Optional[str] = None


class DecisionContent(BaseModel):
    """The AI-owned, LLM-validated output. No numerical authority lives here."""

    model_config = ConfigDict(extra="forbid")

    summary: str
    status_explanation: str
    key_facts: list[DecisionFact] = Field(default_factory=list)
    considerations: list[DecisionConsideration] = Field(default_factory=list)
    options: list[DecisionOption] = Field(default_factory=list)
    data_limitations: list[str] = Field(default_factory=list)
    disclaimer: str


class StructuredDecision(BaseModel):
    """Full decision: LLM content + server-owned metadata."""

    model_config = ConfigDict(extra="forbid")

    summary: str
    status_explanation: str
    key_facts: list[DecisionFact] = Field(default_factory=list)
    considerations: list[DecisionConsideration] = Field(default_factory=list)
    options: list[DecisionOption] = Field(default_factory=list)
    data_limitations: list[str] = Field(default_factory=list)
    disclaimer: str
    ai_metadata: AIMetadata


class WithdrawalDecisionResponse(BaseModel):
    """Deterministic envelope + AI explanation returned by the endpoint."""

    model_config = ConfigDict(extra="forbid")

    requested_amount_minor: int
    requestable: bool
    blocking_reasons: list[str] = Field(default_factory=list)
    current_available_amount_minor: Optional[int] = None
    max_requestable_amount_minor: Optional[int] = None
    snapshot_only: bool = True
    decision: StructuredDecision
