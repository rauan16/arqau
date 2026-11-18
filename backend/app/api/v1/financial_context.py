"""Phase 3.1 Financial Context endpoint.

Authenticated GET /financial/context returning the user's FinancialContext.
Identity comes exclusively from the authenticated user. No caller-controlled
user_id / employee_id / employer_id selectors are accepted.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.schemas.ai_decision import WithdrawalDecisionResponse
from app.schemas.financial_context import (
    FinancialContext,
    WithdrawalAnalysis,
    WithdrawalAnalysisRequest,
)
from app.services.financial_context_service import (
    analyze_withdrawal,
    build_financial_context,
)
from app.services.ai_decision import (
    DecisionAIProvider,
    get_decision_provider,
    make_withdrawal_decision,
)
from app.core.rate_limit import enforce_total_ceiling
from app.api.v1.auth import get_current_user

router = APIRouter(prefix="/financial", tags=["financial"])


async def _require_ai_request(current_user: User = Depends(get_current_user)) -> User:
    """Enforce total AI request ceiling (Tier 2)."""
    await enforce_total_ceiling(str(current_user.id))
    return current_user


@router.get("/context", response_model=FinancialContext)
async def get_financial_context(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    calculation_date: Optional[date] = None,
) -> FinancialContext:
    """Return the authenticated user's authoritative FinancialContext.

    All EWA values are delegated to the Phase 2 EWA engine.
    """
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return await build_financial_context(db, current_user, calculation_date)


@router.post("/withdrawal-analysis", response_model=WithdrawalAnalysis)
async def post_withdrawal_analysis(
    data: WithdrawalAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    calculation_date: Optional[date] = None,
) -> WithdrawalAnalysis:
    """Deterministic, read-only analysis of a hypothetical withdrawal.

    Identity comes exclusively from the authenticated user. The request body
    accepts only a strict positive integer ``amount_minor``; no caller-controlled
    user/employee/employer selectors are accepted. No financial state is mutated
    (no WageAccessRequest is created). Actual withdrawal creation remains the
    responsibility of POST /ewa/request.
    """
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return await analyze_withdrawal(
        db, current_user, data.amount_minor, calculation_date
    )


@router.post("/withdrawal-decision", response_model=WithdrawalDecisionResponse)
async def withdrawal_decision(
    data: WithdrawalAnalysisRequest,
    current_user: User = Depends(_require_ai_request),
    db: AsyncSession = Depends(get_db),
    provider: DecisionAIProvider = Depends(get_decision_provider),
    calculation_date: Optional[date] = None,
) -> WithdrawalDecisionResponse:
    """Phase 3.3 Structured AI Decision endpoint (read-only).

    The deterministic Phase 3.1 + 3.2 pipeline computes every authoritative
    fact. The AI provider only explains those facts and is never trusted to
    compute or override financial state. On any provider problem a
    deterministic, server-owned fallback is returned so the financial
    analysis stays available. No WageAccessRequest is created here.
    """
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return await make_withdrawal_decision(
        db,
        current_user,
        data.amount_minor,
        calculation_date,
        provider,
    )
