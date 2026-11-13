"""Demo AI chat endpoint (public, no authentication required).

POST /demo/ai/chat accepts an arbitrary user question, builds the demo
financial context from trusted server-side seed data, optionally runs the
deterministic withdrawal analysis when the message contains a concrete amount,
optionally searches for real products when the message is shopping-related,
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
import hashlib
import secrets
from typing import Any, Optional
from uuid import uuid4

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
    FALLBACK_TOKEN_LIMIT,
    FALLBACK_UNSAFE_CONTENT,
    FALLBACK_UNSUPPORTED_AMOUNT,
    FakeCopilotProvider,
    OpenAICopilotProvider,
    generate_copilot_answer,
    get_copilot_provider,
    reset_production_provider,
    extract_hypothetical_amount_minor,
    sanitize_provider_payload,
)
from app.services.product_search import (
    get_product_search_service,
    is_shopping_query,
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

# Conversation state (in-memory for demo; in production would use persistent storage)
# Maps conversation_id to {"token": str, "messages": [{"role": "user"|"assistant", "content": str}]}
_converstation_store = {}
_conversations_tokens = {}

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
        FALLBACK_TOKEN_LIMIT: {
            "ru": "Ответ провайдера обрезан лимитом генерации. Показан детерминированный расчёт.",
            "en": "Provider response truncated by generation limit. A deterministic calculation is shown instead.",
        },
    }
    return reasons.get(reason, {}).get(locale, "Показан детерминированный расчёт.")


def _build_demo_authoritative_facts(
    locale: str,
    analysis: Optional[WithdrawalAnalysis] = None,
) -> AuthoritativeCopilotFacts:
    """Build AuthoritativeCopilotFacts from demo context (server-owned)."""
    ctx = build_demo_financial_context()
    earned = ctx.earned_amount * 100
    salary = ctx.salary_amount * 100

    top_categories = [
        SpendingCategoryFact(category="Housing", amount_minor=45_000 * 100, transaction_count=1),
        SpendingCategoryFact(category="Food", amount_minor=(22_000) * 100, transaction_count=1),
        SpendingCategoryFact(category="Transport", amount_minor=14_000 * 100, transaction_count=1),
    ]

    return AuthoritativeCopilotFacts(
        calculation_date=ctx.data_as_of[:10],
        pay_period_start=ctx.payday_date,
        pay_period_end="2026-11-16",
        salary_amount_minor=salary,
        currency=ctx.currency,
        earned_amount_minor=earned,
        policy_limit_minor=0,
        reserved_amount_minor=0,
        paid_amount_minor=0,
        available_amount_minor=0,
        max_requestable_amount_minor=0,
        minimum_withdrawal_minor=None,
        maximum_withdrawal_minor=None,
        # Reserve tracking (period surplus vs target, not actual savings)
        reserve_target_minor=ctx.reserve_target * 100,
        period_net_surplus_minor=ctx.reserve_saved * 100,
        reserve_shortfall_minor=ctx.reserve_remaining * 100,
        reserve_progress_ratio=ctx.reserve_progress,
        eligible=False,
        eligibility_reasons=["NO_EWA_POLICY"],
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
        transaction_count=3,
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
    """Construct a server-owned WithdrawalAnalysis from demo affordability result.

    Uses authoritative EWA availability (0 when no policy) instead of demo ceiling.
    """
    # Get authoritative EWA facts to ensure consistency with authoritative_facts
    authoritative_facts = _build_demo_authoritative_facts("en")
    ewa_available_minor = authoritative_facts.available_amount_minor or 0
    ewa_max_requestable_minor = authoritative_facts.max_requestable_amount_minor or 0

    # Requestability must be consistent with authoritative EWA availability
    # If no EWA policy, nothing is requestable regardless of demo ceiling
    if authoritative_facts.eligible:
        requestable = affordability.requestable
    else:
        requestable = False

    return WithdrawalAnalysis(
        requested_amount_minor=amount_tenge * 100,
        requestability=Requestability(
            requestable=requestable,
            blocking_reasons=[affordability.reason] if affordability.reason else [],
            authoritative_eligibility_reasons=authoritative_facts.eligibility_reasons or [],
        ),
        current_state=CurrentState(
            salary_amount_minor=ctx.salary_amount * 100,
            earned_amount_minor=ctx.earned_amount * 100,
            available_amount_minor=ewa_available_minor,
            max_requestable_amount_minor=ewa_max_requestable_minor,
        ),
        impact=Impact(
            remaining_available_amount_minor=max(0, ewa_available_minor - amount_tenge * 100),
            remaining_max_requestable_amount_minor=max(0, ewa_max_requestable_minor - amount_tenge * 100),
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
    facts: Optional[AuthoritativeCopilotFacts],
    locale: str,
    fallback_reason: str,
    analysis: Optional[WithdrawalAnalysis] = None,
) -> CopilotAnswer:
    """Build a deterministic fallback answer when the provider is unavailable."""
    disclaimer = DEFAULT_DISCLAIMER_RU if locale == "ru" else DEFAULT_DISCLAIMER_EN
    ctx = build_demo_financial_context()

    # Build authoritative facts if not provided (test helper compatibility)
    if facts is None:
        facts = _build_demo_authoritative_facts(locale, analysis=analysis)

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

    ewa_available_kzt = facts.available_amount_minor // 100

    # --- Lead with the answer (system prompt §1) ---
    # Single short conclusion + key number in bold
    if locale == "ru":
        lead = (
            f"Финансовый обзор: за период заработано **{facts.earned_amount_minor // 100} ₸**, "
            f"потрачено **{ctx.expense_amount} ₸**, остаток period surplus — **{ctx.reserve_saved} ₸** "
            f"из целевого резерва **{ctx.reserve_target} ₸** (100%)."
        )
    else:
        lead = (
            f"Financial overview: earned this period **{facts.earned_amount_minor // 100} KZT**, "
            f"expenses **{ctx.expense_amount} KZT**, period surplus **{ctx.reserve_saved} KZT** "
            f"of reserve target **{ctx.reserve_target} KZT** (100%)."
        )

    # --- Key metrics (system prompt §2: compact table with relevant indicators) ---
    # Use structured concise paragraphs; one paragraph per idea
    metrics_ru = (
        f"**Period surplus:** {ctx.reserve_saved} ₸ of **{ctx.reserve_target} ₸** reserve target ({int(ctx.reserve_progress * 100)}%). "
        f"This is earned minus spent, not confirmed bank savings. "
        f"100% means the surplus meets or exceeds the target, not that savings are confirmed. "
        f"**EWA capacity:** {ewa_available_kzt} ₸ (deterministic limit; no EWA policy configured). "
        f"**Expenses this period:** {ctx.expense_amount} ₸ (Housing {ctx.expense_amount_Housing if hasattr(ctx, 'expense_amount_Housing') else ''}₸, "
        f"Food {ctx.expense_amount_Food if hasattr(ctx, 'expense_amount_Food') else ''}₸, "
        f"Transport {ctx.expense_amount_Transport if hasattr(ctx, 'expense_amount_Transport') else ''}₸)."
    )
    metrics_en = (
        f"**Period surplus:** {ctx.reserve_saved} KZT of **{ctx.reserve_target} KZT** reserve target ({int(ctx.reserve_progress * 100)}%). "
        f"This is earned minus spent, not confirmed bank savings. "
        f"100% means the surplus meets or exceeds the target, not that savings are confirmed. "
        f"**EWA capacity:** {ewa_available_kzt} KZT (deterministic limit; no EWA policy configured). "
        f"**Expenses this period:** {ctx.expense_amount} KZT (Housing, Food, Transport)."
    )

    # --- Analysis & status (system prompt §2 order: analysis, then status/limitation) ---
    parts = [lead]

    # Expense breakdown - only relevant categories (Housing 45k, Food 22k, Transport 14k)
    if locale == "ru":
        expense_text = (
            f"Основные статьи расходов: Жилье — 45 000 ₸, "
            f"Еда — 22 000 ₸, Транспорт — 14 000 ₸."
        )
    else:
        expense_text = (
            f"Major expense categories: Housing — 45 000 KZT, "
            f"Food — 22 000 KZT, Transport — 14 000 KZT."
        )
    parts.append(expense_text)

    # EWA education (system prompt §6): explain EWA, role of employer/employee, policy controls
    if locale == "ru":
        ewa_edu = (
            f"EWA (EARned wage access) — это możliwoсть получить часть зарплаты до дня выплаты. "
            f"Политика EWA настраивает работодатель. Сейчас для вашего работодателя "
            f"EWA-политика не настроена, поэтому досрочное получение недоступно. "
            f"Оставшийся лимит EWA — **{ewa_available_kzt} ₸** — это способность системы, "
            f"а не рекомендация или баланс на счете."
        )
    else:
        ewa_edu = (
            f"EWA (Earned Wage Access) — the ability to access a portion of earned wages before "
            f"payday. The EWA policy is configured by the employer. For your employer, "
            f"the EWA policy is not currently configured, so early access is unavailable. "
            f"The remaining EWA limit **{ewa_available_kzt} KZT** is the system's capability, "
            f"not a recommendation or account balance."
        )
    parts.append(ewa_edu)

# Recommendations (system prompt §5: 2-3 specific, actionable recommendations)
    if locale == "ru":
        rec1 = (
            f"1. Проверьте, настроена ли EWA-политика у вашего работодателя — "
            f"без этого досрочного доступа к зарплате не будет доступно."
        )
        rec2 = (
            f"2. Учитывайте, что period surplus {ctx.reserve_saved} ₸ из {ctx.reserve_target} ₸ "
            f"(100%) — это остаток периода, а не гарантированные накопления на банковском счете. "
            f"До тех пор пока резерв не подтвержден."
        )
        rec3 = (
            f"3. Обязательные платежи перед зарплатой ({ctx.upcoming_bills_unpaid_total} ₸) "
            f"могут сказаться на доступных средствах. Рекомендуется сохранить резерв untouched "
            f"перед следующей зарплатой."
        )
    else:
        rec1 = (
            f"1. Check if your employer has an EWA policy configured — without it, "
            f"early wage access will not be available."
        )
        rec2 = (
            f"2. Note that the period surplus {ctx.reserve_saved} KZT of {ctx.reserve_target} KZT "
            f"(100%) is period remainder, not guaranteed funds in a bank account. "
            f"Actual bank savings are not confirmed."
        )
        rec3 = (
            f"3. Upcoming mandatory payments before payday ({ctx.upcoming_bills_unpaid_total} KZT) "
            f"may affect available funds. It is recommended to keep the reserve untouched "
            f"until the next payday."
        )
    parts.append(rec1)
    parts.append(rec2)
    parts.append(rec3)

    # --- Limitation (system prompt §2: status/limitation section) ---
    parts.append(
        f"Limitation: reserve progress ratio of 100% reflects period surplus (earned − expenses), "
        f"not accumulated savings. Actual bank balance and savings are not confirmed."
    )

    # --- Key facts (system prompt §3: keep tables independent, one per heading) ---
    key_facts = [
        CopilotFact(
            code="available_amount",
            text=(
                f"Available: {ewa_available_kzt} KZT (EWA capacity, not a recommendation)."
                if locale == "ru"
                else f"Available: {ewa_available_kzt} KZT (EWA capacity, not a recommendation)."
            ),
        ),
        CopilotFact(
            code="earned_amount",
            text=(
                f"Earned: {facts.earned_amount_minor // 100} KZT."
                if locale == "ru"
                else f"Earned: {facts.earned_amount_minor // 100} KZT."
            ),
        ),
        CopilotFact(
            code="reserve_target",
            text=(
                f"Reserve target: {ctx.reserve_target} KZT, period surplus: {ctx.reserve_saved} KZT."
                if locale == "ru"
                else f"Reserve target: {ctx.reserve_target} KZT, period surplus: {ctx.reserve_saved} KZT."
            ),
        ),
        CopilotFact(
            code="days_to_payday",
            text=(
                f"Days to payday: {ctx.days_to_payday}."
                if locale == "ru"
                else f"Days to payday: {ctx.days_to_payday}."
            ),
        ),
    ]

    return CopilotAnswer(
        response="\n\n".join(parts),
        key_facts=key_facts,
        data_limitations=[
            "Reserve progress 100% reflects period surplus, not confirmed savings.",
            "EWA availability is deterministic capacity, not a recommended withdrawal amount.",
            "Actual bank balance and savings are not confirmed.",
        ],
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


def _get_demo_housing_expense() -> int:
    """Return the demo housing expense amount."""
    return 45_000


def _get_demo_food_expense() -> int:
    """Return the demo food expense amount."""
    return 22_000


def _get_demo_transport_expense() -> int:
    """Return the demo transport expense amount."""
    return 14_000


@router.post("/chat", response_model=CopilotResponse)
async def demo_chat_endpoint(
    request: ChatRequest,
    provider: CopilotProvider = Depends(get_copilot_provider),
    _rate_limit: None = Depends(enforce_demo_ai_rate_limit),
) -> CopilotResponse:
    """Public demo AI chat. No authentication required.

    Builds the demo financial context from trusted server-side seed data,
    optionally analyses a hypothetical amount found in the message,
    optionally searches for real products when the message is shopping-related,
    and returns a structured CopilotResponse.
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

    # Optionally search for products if the query is shopping-related.
    product_search_results = []
    if is_shopping_query(message):
        try:
            search_service = get_product_search_service()
            search_result = await search_service.search(message, limit=5)
            if search_result.offers:
                product_search_results = [
                    {
                        "source": o.source,
                        "product_id": o.product_id,
                        "title": o.title,
                        "price_minor": o.price_minor,
                        "currency": o.currency,
                        "seller": o.seller,
                        "url": o.url,
                        "availability": o.availability,
                        "delivery_info": o.delivery_info,
                    }
                    for o in search_result.offers
                ]
        except Exception:  # noqa: BLE001
            # Product search is best-effort; don't fail the chat if it errors
            pass

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
    # Add product search results if available (not part of analysis)
    if product_search_results:
        payload["product_search_results"] = product_search_results
    payload = sanitize_provider_payload(payload)

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
        fallback_answer = _build_demo_fallback_answer(facts, locale, answer.ai_metadata.fallback_reason or FALLBACK_HTTP_ERROR, analysis)
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
        product_search_results=product_search_results,
        conversation_id=request.conversation_id,
        conversation_persisted=False,
        ai_metadata=answer.ai_metadata,
        read_only=True,
        snapshot_only=True,
    )
