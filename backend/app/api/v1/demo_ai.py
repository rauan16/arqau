"""Demo AI chat endpoint (public, no authentication required).

POST /demo/ai/chat accepts an arbitrary user question, builds the demo
financial context from trusted server-side seed data, optionally runs the
deterministic withdrawal analysis when the message contains a concrete amount,
and returns a structured CopilotResponse.

The LLM provider (OpenAI / OpenRouter) is called only server-side via
OPENAI_API_KEY. If the key is not configured, a deterministic fallback is
returned instead. The client never receives raw provider errors and never
supplies trusted financial values.

Read-only: creates no WageAccessRequest, mutates no financial state, and
never touches authenticated user data.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import StringConstraints
from typing_extensions import Annotated

from app.services.ai_copilot import (
    CopilotProvider,
    FALLBACK_CONNECTION,
    FALLBACK_HTTP_ERROR,
    FALLBACK_MALFORMED,
    FALLBACK_NOT_CONFIGURED,
    FALLBACK_RATE_LIMIT,
    FALLBACK_SCHEMA_INVALID,
    FALLBACK_TIMEOUT,
    FALLBACK_UNSAFE_CONTENT,
    FALLBACK_UNSUPPORTED_AMOUNT,
    FakeCopilotProvider,
    OpenAICopilotProvider,
    generate_copilot_answer,
    get_copilot_provider,
    reset_production_provider,
    extract_hypothetical_amount_minor,
)
from app.core.rate_limit import enforce_demo_ai_rate_limit
from app.services.demo_financial_context import (
    build_demo_financial_context,
    build_demo_sanitized_input,
    evaluate_demo_affordability,
)
from app.schemas.ai import ChatRequest
from app.schemas.ai_copilot import (
    AuthoritativeCopilotFacts,
    CopilotAnswer,
    CopilotFact,
    CopilotMetadata,
    CopilotResponse,
    SpendingCategoryFact,
)
from app.schemas.financial_context import (
    BudgetImpact,
    CurrentState,
    DataQualityAnalysis,
    Impact,
    Requestability,
    WithdrawalAnalysis,
    WithdrawalFrequency,
)

router = APIRouter(prefix="/demo/ai", tags=["demo-ai"])

MAX_MESSAGE_CHARS = 2000
DEMO_USER_ID = "demo"

DEFAULT_DISCLAIMER_RU = (
    "Это иллюстративное объяснение, а не финансовый совет. "
    "ARQAU не гарантирует какой-либо конкретный финансовый результат."
)
DEFAULT_DISCLAIMER_EN = (
    "This is illustrative guidance, not financial advice. "
    "ARQAU does not guarantee any specific financial outcome."
)

DEFAULT_SUGGESTED_QUESTIONS_RU = [
    "Могу ли я купить авиабилет Алматы — Астана за 45 000 ₸?",
    "Сколько денег у меня останется после этой покупки?",
    "Какие обязательные платежи мне предстоят?",
    "Сколько я могу потратить, чтобы сохранить резерв?",
    "Что лучше: купить сейчас или дождаться зарплаты?",
]
DEFAULT_SUGGESTED_QUESTIONS_EN = [
    "Can I buy a flight Almaty — Astana for 45,000 ₸?",
    "How much money will I have left after this purchase?",
    "What upcoming mandatory payments do I have?",
    "How much can I spend while keeping my reserve?",
    "Should I buy now or wait for payday?",
]


def _fallback_reason_text(reason: str, locale: str) -> str:
    reasons = {
        FALLBACK_NOT_CONFIGURED: {
            "ru": "AI-провайдер не настроен (нет OPENAI_API_KEY). Показан детерминированный расчёт.",
            "en": "AI provider is not configured (no OPENAI_API_KEY). A deterministic calculation is shown instead.",
        },
        FALLBACK_TIMEOUT: {
            "ru": "Провайдер не ответил вовремя. Показан детерминированный расчёт.",
            "en": "The provider did not respond in time. A deterministic calculation is shown instead.",
        },
        FALLBACK_CONNECTION: {
            "ru": "Ошибка подключения к провайдеру. Показан детерминированный расчёт.",
            "en": "Connection error to the provider. A deterministic calculation is shown instead.",
        },
        FALLBACK_RATE_LIMIT: {
            "ru": "Превышен лимит провайдера. Показан детерминированный расчёт.",
            "en": "Provider rate limit reached. A deterministic calculation is shown instead.",
        },
        FALLBACK_HTTP_ERROR: {
            "ru": "Ошибка провайдера. Показан детерминированный расчёт.",
            "en": "Provider error. A deterministic calculation is shown instead.",
        },
        FALLBACK_MALFORMED: {
            "ru": "Некорректный ответ от провайдера. Показан детерминированный расчёт.",
            "en": "Malformed response from the provider. A deterministic calculation is shown instead.",
        },
        FALLBACK_SCHEMA_INVALID: {
            "ru": "Ответ провайдера не прошёл валидацию. Показан детерминированный расчёт.",
            "en": "Provider response failed validation. A deterministic calculation is shown instead.",
        },
        FALLBACK_UNSAFE_CONTENT: {
            "ru": "Ответ провайдера не прошёл проверку безопасности. Показан детерминированный расчёт.",
            "en": "Provider response failed safety check. A deterministic calculation is shown instead.",
        },
        FALLBACK_UNSUPPORTED_AMOUNT: {
            "ru": "В ответе провайдера обнаружена Unsupported сумма. Показан детерминированный расчёт.",
            "en": "Unsupported amount detected in provider response. A deterministic calculation is shown instead.",
        },
    }
    return reasons.get(reason, {}).get(locale, "Показан детерминированный расчёт.")


def _build_demo_authoritative_facts(
    locale: str,
    analysis: Optional[WithdrawalAnalysis] = None,
) -> AuthoritativeCopilotFacts:
    """Build AuthoritativeCopilotFacts from demo context (server-owned)."""
    ctx = build_demo_financial_context()
    ewa_available = ctx.available_amount * 100
    earned = ctx.earned_amount * 100
    salary = ctx.salary_amount * 100

    top_categories = [
        SpendingCategoryFact(category="Housing", amount_minor=45_000 * 100, transaction_count=1),
        SpendingCategoryFact(category="Food", amount_minor=37_400 * 100, transaction_count=2),
        SpendingCategoryFact(category="Transport", amount_minor=15_000 * 100, transaction_count=1),
        SpendingCategoryFact(category="Health", amount_minor=13_000 * 100, transaction_count=1),
        SpendingCategoryFact(category="Lifestyle", amount_minor=6_500 * 100, transaction_count=1),
    ]

    return AuthoritativeCopilotFacts(
        calculation_date=ctx.data_as_of[:10],
        pay_period_start=ctx.payday_date,
        pay_period_end="2026-10-15",
        salary_amount_minor=salary,
        currency=ctx.currency,
        earned_amount_minor=earned,
        policy_limit_minor=0,
        reserved_amount_minor=0,
        paid_amount_minor=0,
        available_amount_minor=ewa_available,
        max_requestable_amount_minor=ewa_available,
        minimum_withdrawal_minor=None,
        maximum_withdrawal_minor=None,
        eligible=ctx.available_amount > 0,
        eligibility_reasons=[],
        can_request_withdrawal=False,
        withdrawals_this_period=0,
        max_withdrawals_per_period=None,
        total_withdrawal_requests=0,
        pending_withdrawal_count=0,
        approved_withdrawal_count=0,
        paid_withdrawal_count=0,
        paid_withdrawal_amount_minor=0,
        spending_available=True,
        total_spending_minor=ctx.expense_amount * 100,
        transaction_count=8,
        top_spending_categories=top_categories,
        budget_available=False,
        budget_total_minor=None,
        budget_spent_minor=None,
        budget_remaining_minor=None,
        goals_available=False,
        active_goals_count=0,
        total_goal_target_minor=None,
        total_goal_saved_minor=None,
        has_salary_profile=True,
        has_ewa_policy=False,
        has_transactions=True,
        has_budget=False,
        has_goals=False,
        missing_data=[],
        availability_note=(
            "available_amount_minor is deterministic remaining EWA capacity, not a "
            "recommended amount."
        ),
    )


def _build_demo_affordability_analysis(
    amount_tenge: int,
    affordability: Any,
    ctx: Any,
) -> WithdrawalAnalysis:
    """Construct a server-owned WithdrawalAnalysis from demo affordability result."""
    return WithdrawalAnalysis(
        requested_amount_minor=amount_tenge * 100,
        requestability=Requestability(
            requestable=affordability.requestable,
            blocking_reasons=[affordability.reason] if affordability.reason else [],
            authoritative_eligibility_reasons=[],
        ),
        current_state=CurrentState(
            salary_amount_minor=ctx.salary_amount * 100,
            earned_amount_minor=ctx.earned_amount * 100,
            available_amount_minor=ctx.available_amount * 100,
            max_requestable_amount_minor=ctx.available_amount * 100,
        ),
        impact=Impact(
            remaining_available_amount_minor=affordability.remaining_available * 100,
            remaining_max_requestable_amount_minor=affordability.remaining_available * 100,
            requested_share_of_earned_bps=round(affordability.share_of_earned * 10000),
            exposure_after_minor=affordability.amount * 100,
        ),
        withdrawal_frequency=WithdrawalFrequency(
            withdrawals_this_period=0,
            max_withdrawals_per_period=None,
        ),
        budget_impact=BudgetImpact(),
        data_quality=DataQualityAnalysis(),
        snapshot_only=True,
    )


def _build_demo_fallback_answer(
    facts: AuthoritativeCopilotFacts,
    locale: str,
    fallback_reason: str,
) -> CopilotAnswer:
    """Build a deterministic fallback answer when the provider is unavailable."""
    disclaimer = DEFAULT_DISCLAIMER_RU if locale == "ru" else DEFAULT_DISCLAIMER_EN
    ctx = build_demo_financial_context()

    if fallback_reason == FALLBACK_NOT_CONFIGURED:
        intro = (
            "AI-провайдер не настроен на сервере. "
            "Ниже показан детерминированный финансовый расчёт без участия модели."
            if locale == "ru"
            else "The AI provider is not configured on the server. "
            "A deterministic financial calculation is shown below without model involvement."
        )
    else:
        intro = _fallback_reason_text(fallback_reason, locale)

    parts = [intro]
    parts.append(
        f"Доступно к выводу: {ctx.available_amount} ₸."
        if locale == "ru"
        else f"Available to access: {ctx.available_amount} ₸."
    )
    parts.append(
        f"Заработано в этом периоде: {ctx.earned_amount} ₸."
        if locale == "ru"
        else f"Earned this period: {ctx.earned_amount} ₸."
    )
    parts.append(
        f"Целевой резерв: {ctx.reserve_target} ₸, накоплено: {ctx.reserve_saved} ₸."
        if locale == "ru"
        else f"Reserve target: {ctx.reserve_target} ₸, saved: {ctx.reserve_saved} ₸."
    )
    parts.append(
        f"Предстоящие счета: {ctx.upcoming_bills_total} ₸ (из них неоплаченные: {ctx.upcoming_bills_unpaid_total} ₸)."
        if locale == "ru"
        else f"Upcoming bills: {ctx.upcoming_bills_total} ₸ (unpaid: {ctx.upcoming_bills_unpaid_total} ₸)."
    )
    parts.append(
        f"До зарплаты: {ctx.days_to_payday} дней."
        if locale == "ru"
        else f"Days to payday: {ctx.days_to_payday}."
    )

    key_facts = [
        CopilotFact(
            code="available_amount",
            text=(
                f"Доступно: {ctx.available_amount} ₸ (ёмкость EWA, не рекомендация к выводу)."
                if locale == "ru"
                else f"Available: {ctx.available_amount} ₸ (EWA capacity, not a recommendation)."
            ),
        ),
        CopilotFact(
            code="earned_amount",
            text=(
                f"Заработано: {ctx.earned_amount} ₸."
                if locale == "ru"
                else f"Earned: {ctx.earned_amount} ₸."
            ),
        ),
        CopilotFact(
            code="reserve_target",
            text=(
                f"Целевой резерв: {ctx.reserve_target} ₸, накоплено: {ctx.reserve_saved} ₸."
                if locale == "ru"
                else f"Reserve target: {ctx.reserve_target} ₸, saved: {ctx.reserve_saved} ₸."
            ),
        ),
        CopilotFact(
            code="upcoming_bills",
            text=(
                f"Предстоящие счета: {ctx.upcoming_bills_total} ₸."
                if locale == "ru"
                else f"Upcoming bills: {ctx.upcoming_bills_total} ₸."
            ),
        ),
        CopilotFact(
            code="days_to_payday",
            text=(
                f"До зарплаты: {ctx.days_to_payday} дн."
                if locale == "ru"
                else f"Days to payday: {ctx.days_to_payday}."
            ),
        ),
    ]

    return CopilotAnswer(
        response=" ".join(parts),
        key_facts=key_facts,
        data_limitations=[f"AI-провайдер недоступен: {fallback_reason}. Показан только детерминированный расчёт."],
        suggested_questions=DEFAULT_SUGGESTED_QUESTIONS_RU if locale == "ru" else DEFAULT_SUGGESTED_QUESTIONS_EN,
        disclaimer=disclaimer,
        ai_metadata=CopilotMetadata(
            generated=False,
            fallback_used=True,
            provider=None,
            model=None,
            fallback_reason=fallback_reason,
        ),
    )


@router.post("/chat", response_model=CopilotResponse)
async def demo_chat_endpoint(
    request: ChatRequest,
    provider: CopilotProvider = Depends(get_copilot_provider),
    _rate_limit: None = Depends(enforce_demo_ai_rate_limit),
) -> CopilotResponse:
    """Public demo AI chat. No authentication required.

    Builds the demo financial context from trusted server-side seed data,
    optionally analyses a hypothetical amount found in the message, and
    returns a structured answer (LLM-generated or deterministic fallback).
    """
    message = (request.message or "").strip()
    if not message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message is required",
        )
    if len(message) > MAX_MESSAGE_CHARS:
        message = message[:MAX_MESSAGE_CHARS]

    # Detect locale from message (simple heuristic: Cyrillic = Russian)
    locale = "ru" if re.search(r"[а-яА-Я]", message) else "en"

    # Build authoritative facts from trusted server-side demo context.
    facts = _build_demo_authoritative_facts(locale)

    # Optionally analyse a hypothetical withdrawal/purchase amount.
    analysis: Optional[WithdrawalAnalysis] = None
    amount_minor = extract_hypothetical_amount_minor(message)
    if amount_minor is not None:
        ctx = build_demo_financial_context()
        affordability = evaluate_demo_affordability(amount_minor // 100)
        analysis = _build_demo_affordability_analysis(amount_minor // 100, affordability, ctx)
        facts = _build_demo_authoritative_facts(locale, analysis=analysis)

    # Build sanitized provider input (server-owned facts only).
    payload = build_demo_sanitized_input(
        {
            "amount": analysis.requested_amount_minor // 100 if analysis else 0,
            "requestable": analysis.requestability.requestable if analysis else False,
            "reason": analysis.requestability.blocking_reasons[0] if analysis and analysis.requestability.blocking_reasons else None,
            "remaining_available": analysis.impact.remaining_available_amount_minor // 100 if analysis and analysis.impact.remaining_available_amount_minor else 0,
            "share_of_earned": (analysis.impact.requested_share_of_earned_bps or 0) / 10000 if analysis else 0,
            "status": "comfortable" if analysis and analysis.requestability.requestable else "caution",
        } if analysis else None,
    )

    # Run the provider pipeline with safety guards and deterministic fallback.
    # `generate_copilot_answer` handles: not_configured, timeout, connection,
    # rate limit, HTTP error, malformed response, schema invalid, unsafe
    # content, unsupported amount — all falling back deterministically.
    answer = await generate_copilot_answer(
        provider=provider,
        payload=payload,
        facts=facts,
        user_message=message,
        user_id=DEMO_USER_ID,
        analysis=analysis,
    )

    # Override locale-specific fields that `generate_copilot_answer` sets to
    # English defaults (disclaimer, suggested questions).
    disclaimer = DEFAULT_DISCLAIMER_RU if locale == "ru" else DEFAULT_DISCLAIMER_EN
    suggested = DEFAULT_SUGGESTED_QUESTIONS_RU if locale == "ru" else DEFAULT_SUGGESTED_QUESTIONS_EN

    # Build a locale-aware fallback answer when the provider was unavailable.
    if answer.ai_metadata.fallback_used:
        fallback_answer = _build_demo_fallback_answer(facts, locale, answer.ai_metadata.fallback_reason or FALLBACK_HTTP_ERROR)
        # Preserve provider/model attribution from the answer.
        fallback_answer.ai_metadata.provider = answer.ai_metadata.provider
        fallback_answer.ai_metadata.model = answer.ai_metadata.model
        answer = fallback_answer

    return CopilotResponse(
        response=answer.response,
        key_facts=answer.key_facts,
        data_limitations=answer.data_limitations,
        suggested_questions=suggested,
        disclaimer=disclaimer,
        authoritative_facts=facts,
        withdrawal_analysis=analysis,
        conversation_id=request.conversation_id,
        conversation_persisted=False,
        ai_metadata=answer.ai_metadata,
        read_only=True,
        snapshot_only=True,
    )
