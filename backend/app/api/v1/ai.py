"""AI endpoints (Phase 3.4 Financial Copilot).

Both endpoints sit on top of the authoritative deterministic pipeline:

    FinancialContext (Phase 3.1)
        -> deterministic withdrawal analysis (Phase 3.2)
            -> safe AI explanation (Phase 3.3 / Phase 3.4)

Neither endpoint creates a WageAccessRequest, approves a withdrawal, or mutates
any financial state. Both are read-only snapshots.

- POST /ai/chat is the Financial Copilot. Its entire authoritative input comes
  from `build_financial_context`; the LLM only writes explanatory prose.
- POST /ai/analyze-withdrawal is deprecated and now delegates to the Phase 3.3
  decision service. It no longer reads the legacy `EarnedWages` table, no
  longer sums transactions, and no longer asks the LLM to determine risk,
  recommendation, reserve status, or expense coverage.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.database import get_db
from app.models import User
from app.schemas.ai import ChatRequest
from app.schemas.ai_copilot import CopilotResponse
from app.schemas.ai_decision import WithdrawalDecisionResponse
from app.services.ai_copilot import CopilotProvider, answer_copilot_query, get_copilot_provider
from app.services.ai_decision import (
    DecisionAIProvider,
    get_decision_provider,
    make_withdrawal_decision,
)
from app.core.rate_limit import enforce_total_ceiling

router = APIRouter(prefix="/ai", tags=["ai"])


async def _require_ai_request(current_user: User = Depends(get_current_user)) -> User:
    """Enforce total AI request ceiling (Tier 2)."""
    await enforce_total_ceiling(str(current_user.id))
    return current_user


@router.post("/chat", response_model=CopilotResponse)
async def chat_endpoint(
    request: ChatRequest,
    current_user: User = Depends(_require_ai_request),
    db: AsyncSession = Depends(get_db),
    provider: CopilotProvider = Depends(get_copilot_provider),
    calculation_date: Optional[date] = None,
) -> CopilotResponse:
    """Phase 3.4 Financial Copilot endpoint (read-only).

    Builds the authoritative Phase 3.1 FinancialContext for the authenticated
    user, sanitizes an allow-listed fact payload for the provider, and returns a
    structured answer whose authoritative numeric fields are assembled
    server-side.

    On any provider problem — missing configuration, timeout, connection
    failure, rate limit, HTTP failure, malformed output, or schema violation —
    a deterministic, server-owned answer is returned instead of an error, so
    the financial snapshot always stays available and internal provider errors
    are never exposed.
    """
    return await answer_copilot_query(
        db,
        current_user,
        request.message,
        request.conversation_id,
        calculation_date,
        provider,
    )


def _extract_withdrawal_amount(payload: dict[str, Any]) -> int:
    """Accept the legacy `withdrawal_amount` and the newer `amount_minor` key."""
    raw = payload.get("withdrawal_amount")
    if raw is None:
        raw = payload.get("amount_minor")
    if raw is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="withdrawal_amount is required",
        )
    try:
        amount = int(raw)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="withdrawal_amount must be an integer",
        )
    if amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="withdrawal_amount must be positive",
        )
    return amount


@router.post(
    "/analyze-withdrawal",
    response_model=WithdrawalDecisionResponse,
    deprecated=True,
)
async def analyze_withdrawal_endpoint(
    request: dict,
    current_user: User = Depends(_require_ai_request),
    db: AsyncSession = Depends(get_db),
    provider: DecisionAIProvider = Depends(get_decision_provider),
    calculation_date: Optional[date] = None,
) -> WithdrawalDecisionResponse:
    """Deprecated: use POST /financial/withdrawal-analysis or
    POST /financial/withdrawal-decision.

    Retained for API compatibility. Request validation (missing, non-integer,
    or non-positive amount -> 400) and authentication (401) are unchanged.

    The response body is now the authoritative Phase 3.3
    `WithdrawalDecisionResponse`. Two legacy behaviours are intentionally gone,
    because both were AI-side financial calculation rather than backend
    validation:

    - the `EarnedWages`-based "no earned wages found" / "amount exceeds
      available balance" 400s are replaced by the deterministic Phase 3.2
      blocking reasons, which are returned as data (HTTP 200),
    - the LLM no longer decides `risk_level`, `recommendation`,
      `reserve_status`, or `covered_expenses`; those fields are removed because
      the backend must not take financial advice from a model.

    Read-only: no WageAccessRequest is created.
    """
    amount_minor = _extract_withdrawal_amount(request)
    return await make_withdrawal_decision(
        db, current_user, amount_minor, calculation_date, provider
    )