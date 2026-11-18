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

from dataclasses import asdict
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
    is_purchase_affordability_question,
    is_withdrawal_question,
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
    evaluate_demo_purchase_affordability,
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
        upcoming_bills_total_minor=ctx.upcoming_bills_total * 100,
        upcoming_bills_unpaid_minor=ctx.upcoming_bills_unpaid_total * 100,
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


def _format_demo_purchase_money(amount_minor: int, locale: str) -> str:
    amount = amount_minor // 100
    formatted = f"{amount:,}"
    return formatted.replace(",", " ") if locale == "ru" else formatted


def _is_available_funds_question(message: str) -> bool:
    """Recognize direct questions about funds currently available to the user.

    Keep this separate from EWA withdrawal intent: a generic available-money
    question must not be answered with an EWA limit or a broad financial report.
    """
    normalized = re.sub(r"\\s+", " ", (message or "").strip().lower())
    patterns = (
        r"\\bhow much (?:money|cash|funds) do i have available\\b",
        r"\\bhow much (?:money|cash|funds) (?:is )?available\\b",
        r"\\bwhat (?:is|are) (?:my )?available (?:balance|funds|cash)\\b",
        r"\\bwhat(?:'s| is) my available (?:balance|funds|cash)\\b",
        r"\\bсколько у меня (?:есть )?(?:денег|средств) (?:сейчас )?(?:доступно|в наличии)\\b",
        r"\\bсколько (?:денег|средств) (?:у меня )?(?:доступно|в наличии)\\b",
        r"\\bкакой у меня доступный (?:баланс|остаток)\\b",
        r"\\bкакой доступный (?:баланс|остаток)\\b",
    )
    return any(re.search(pattern, normalized) for pattern in patterns)


def _build_demo_available_funds_fallback_answer(
    facts: Optional[AuthoritativeCopilotFacts],
    locale: str,
    fallback_reason: str,
    analysis: dict[str, Any],
) -> CopilotAnswer:
    """Answer available-funds questions without conflating cash, headroom and EWA."""
    if facts is None:
        facts = _build_demo_authoritative_facts(locale)

    fmt = lambda key: _format_demo_purchase_money(int(analysis[key]), locale)
    surplus = fmt("period_surplus_minor")
    bills = fmt("upcoming_bills_unpaid_minor")
    after_bills = fmt("amount_after_bills_minor")
    reserve = fmt("reserve_target_minor")
    headroom = fmt("purchase_headroom_minor")
    ewa_available = _format_demo_purchase_money(
        facts.available_amount_minor or 0, locale
    )

    if locale == "ru":
        if int(analysis["purchase_headroom_minor"]) > 0:
            lead = (
                f"По расчету демо-профиля после обязательных платежей и целевого резерва "
                f"остается до **{headroom} ₸** свободного запаса."
            )
        else:
            lead = (
                "По расчету демо-профиля после обязательных платежей и целевого резерва "
                "свободного запаса для дополнительных трат не остается."
            )
        detail = (
            f"Расчет: остаток периода — **{surplus} ₸**; после неоплаченных счетов "
            f"на **{bills} ₸** остается **{after_bills} ₸**; целевой резерв — "
            f"**{reserve} ₸**."
        )
        cash_note = (
            "Это расчетный запас по денежному потоку, а не подтвержденный баланс счета. "
            "Фактический банковский баланс и отдельные накопления в демо-профиле неизвестны."
        )
        ewa_note = (
            f"Доступная сумма EWA — **{ewa_available} ₸**: работодатель не настроил "
            "политику досрочной выплаты. Это отдельный показатель, не банковский баланс."
        )
        fallback_note = "Показан серверный детерминированный расчет; AI-пояснение сейчас недоступно."
        facts_text = [
            f"Свободный запас после счетов и целевого резерва: {headroom} ₸.",
            f"Доступная сумма EWA: {ewa_available} ₸.",
            "Фактический банковский баланс в демо-профиле неизвестен.",
        ]
        limitations = [
            "Фактический банковский баланс и отдельные накопления в демо-профиле не подтверждены.",
            "Свободный запас рассчитан по данным демо-профиля и не является подтвержденными деньгами на счете.",
            "EWA недоступен, поскольку работодатель не настроил политику досрочной выплаты.",
        ]
    else:
        if int(analysis["purchase_headroom_minor"]) > 0:
            lead = (
                "Based on the demo profile, up to "
                f"**{headroom} KZT** remains as planning headroom after upcoming bills "
                "and the reserve target."
            )
        else:
            lead = (
                "Based on the demo profile, no planning headroom remains for additional "
                "spending after upcoming bills and the reserve target."
            )
        detail = (
            f"Calculation: period surplus is **{surplus} KZT**; after **{bills} KZT** "
            f"in unpaid bills, **{after_bills} KZT** remains; the reserve target is "
            f"**{reserve} KZT**."
        )
        cash_note = (
            "This is a period cash-flow estimate, not a confirmed account balance. "
            "Your actual bank balance and separate savings are unknown in the demo profile."
        )
        ewa_note = (
            f"Available EWA is **{ewa_available} KZT** because the employer has not "
            "configured an early-wage-access policy. This is separate from your bank balance."
        )
        fallback_note = (
            "This is a server-side deterministic calculation; the AI explanation is currently unavailable."
        )
        facts_text = [
            f"Planning headroom after bills and reserve: {headroom} KZT.",
            f"Available EWA amount: {ewa_available} KZT.",
            "Actual bank balance is not available in the demo profile.",
        ]
        limitations = [
            "Actual bank balance and separate savings are not confirmed in the demo profile.",
            "Planning headroom is calculated from demo data and is not confirmed cash in the account.",
            "EWA is unavailable because the employer policy is not configured.",
        ]

    return CopilotAnswer(
        response="\\n\\n".join((lead, detail, cash_note, ewa_note, fallback_note)),
        key_facts=[
            CopilotFact(code="available_amount", text=facts_text[0]),
            CopilotFact(code="ewa_available_amount", text=facts_text[1]),
            CopilotFact(code="bank_balance", text=facts_text[2]),
        ],
        data_limitations=limitations,
        suggested_questions=(
            DEFAULT_SUGGESTED_QUESTIONS_RU
            if locale == "ru"
            else DEFAULT_SUGGESTED_QUESTIONS_EN
        ),
        disclaimer=(
            DEFAULT_DISCLAIMER_RU if locale == "ru" else DEFAULT_DISCLAIMER_EN
        ),
        ai_metadata=CopilotMetadata(
            generated=False,
            fallback_used=True,
            provider=None,
            model=None,
            fallback_reason=fallback_reason,
        ),
    )


def _build_demo_purchase_fallback_answer(
    locale: str,
    fallback_reason: str,
    purchase_analysis: dict[str, Any],
) -> CopilotAnswer:
    """Build a direct deterministic answer from the server-side purchase calculation."""
    fmt = lambda key: _format_demo_purchase_money(int(purchase_analysis[key]), locale)

    purchase_minor = purchase_analysis.get("purchase_amount_minor")
    surplus = fmt("period_surplus_minor")
    bills = fmt("upcoming_bills_unpaid_minor")
    after_bills = fmt("amount_after_bills_minor")
    reserve = fmt("reserve_target_minor")
    headroom = fmt("purchase_headroom_minor")

    if purchase_minor is None:
        if locale == "ru":
            lead = (
                f"По денежному потоку демо-профиля на покупку остается до **{headroom} ₸** "
                "после учета обязательных платежей и целевого резерва."
            )
            detail = (
                f"Остаток периода — **{surplus} ₸**. После неоплаченных счетов "
                f"на **{bills} ₸** остается **{after_bills} ₸**; целевой резерв — "
                f"**{reserve} ₸**."
            )
            follow_up = "Для оценки конкретной покупки нужна ее цена."
            limitation = (
                "Это оценка по денежному потоку, а не подтвержденные деньги на счете. "
                "Фактический банковский баланс и накопления неизвестны."
            )
            fallback_note = "Показан серверный расчет: AI-пояснение сейчас недоступно."
        else:
            lead = (
                f"The demo profile leaves up to **{headroom} KZT** for a purchase "
                "after upcoming bills and the reserve target are accounted for."
            )
            detail = (
                f"The period-surplus indicator is **{surplus} KZT**. After "
                f"**{bills} KZT** in unpaid bills, **{after_bills} KZT** remains "
                f"before preserving the **{reserve} KZT** reserve target."
            )
            follow_up = "Share the purchase price to assess that specific item."
            limitation = (
                "This is a period-flow estimate, not confirmed cash in your account. "
                "Your actual bank balance and savings are unknown."
            )
            fallback_note = (
                "This is the server-calculated estimate; the AI explanation is currently unavailable."
            )
        response = "\n\n".join((lead, detail, follow_up, fallback_note))
    else:
        purchase = _format_demo_purchase_money(int(purchase_minor), locale)
        if purchase_analysis.get("fits_period_buffer"):
            remaining = fmt("remaining_after_purchase_and_bills_minor")
            if locale == "ru":
                lead = (
                    f"По расчету денежного потока демо-профиля покупка за **{purchase} ₸** "
                    "укладывается в запас после оплаты предстоящих счетов и сохранения целевого резерва."
                )
                detail = (
                    f"Остаток периода — **{surplus} ₸**. После неоплаченных счетов "
                    f"на **{bills} ₸** и покупки расчетный остаток составит **{remaining} ₸**, "
                    f"при целевом резерве **{reserve} ₸**."
                )
                limitation = (
                    "Это оценка денежного потока, а не подтвержденные деньги на счете. "
                    "Фактический банковский баланс и отдельные накопления неизвестны."
                )
                fallback_note = "Показан серверный расчет: AI-пояснение сейчас недоступно."
            else:
                lead = (
                    f"Based on the demo profile's period cash-flow estimate, a **{purchase} KZT** "
                    "purchase fits after covering upcoming bills and preserving the reserve target."
                )
                detail = (
                    f"The period-surplus indicator is **{surplus} KZT**. After "
                    f"**{bills} KZT** in unpaid bills and this purchase, the calculated "
                    f"remainder is **{remaining} KZT**, with a **{reserve} KZT** reserve target."
                )
                limitation = (
                    "This is a cash-flow estimate, not confirmed money in your account. "
                    "Your actual bank balance and separate savings are unknown."
                )
                fallback_note = (
                    "This is the server-calculated estimate; the AI explanation is currently unavailable."
                )
            response = "\n\n".join((lead, detail, fallback_note))
        else:
            shortfall = fmt("shortfall_minor")
            if locale == "ru":
                lead = (
                    f"По расчету денежного потока демо-профиля покупка за **{purchase} ₸** "
                    "не укладывается в запас после оплаты предстоящих счетов и сохранения резерва."
                )
                detail = (
                    f"Остаток периода — **{surplus} ₸**. После неоплаченных счетов "
                    f"на **{bills} ₸** остается **{after_bills} ₸**. Если сохранить "
                    f"целевой резерв **{reserve} ₸**, на покупку остается до **{headroom} ₸**."
                )
                gap = (
                    f"Покупка превышает этот запас на **{shortfall} ₸**. "
                    "Это оценка демо-денежного потока, а не проверка банковского счета."
                )
                limitation = (
                    "Фактический баланс и накопления на банковском счете неизвестны. "
                    "Отдельные сбережения, не отраженные в демо-профиле, могут изменить вывод."
                )
                fallback_note = "Показан серверный расчет: AI-пояснение сейчас недоступно."
            else:
                lead = (
                    f"Based on the demo profile's period cash-flow estimate, a **{purchase} KZT** "
                    "purchase does not fit while covering upcoming bills and preserving the reserve."
                )
                detail = (
                    f"The period-surplus indicator is **{surplus} KZT**. After "
                    f"**{bills} KZT** in unpaid bills, **{after_bills} KZT** remains. "
                    f"Preserving the **{reserve} KZT** reserve target leaves up to "
                    f"**{headroom} KZT** for the purchase."
                )
                gap = (
                    f"The purchase exceeds that buffer by **{shortfall} KZT**. "
                    "This is a demo cash-flow estimate, not a check of your bank account."
                )
                limitation = (
                    "The actual bank balance and savings are unknown. Separate savings "
                    "not represented in the demo profile could change the conclusion."
                )
                fallback_note = (
                    "This is the server-calculated estimate; the AI explanation is currently unavailable."
                )
            response = "\n\n".join((lead, detail, gap, fallback_note))

    return CopilotAnswer(
        response=response,
        key_facts=[
            CopilotFact(
                code="surplus_summary",
                text=(
                    f"Показатель остатка периода: {surplus} ₸."
                    if locale == "ru"
                    else f"Period-surplus indicator: {surplus} KZT."
                ),
            ),
            CopilotFact(
                code="upcoming_bills",
                text=(
                    f"Неоплаченные обязательные платежи: {bills} ₸."
                    if locale == "ru"
                    else f"Unpaid upcoming bills: {bills} KZT."
                ),
            ),
            CopilotFact(
                code="reserve_target",
                text=(
                    f"Целевой резерв: {reserve} ₸."
                    if locale == "ru"
                    else f"Reserve target: {reserve} KZT."
                ),
            ),
        ],
        data_limitations=[limitation],
        suggested_questions=(
            DEFAULT_SUGGESTED_QUESTIONS_RU
            if locale == "ru"
            else DEFAULT_SUGGESTED_QUESTIONS_EN
        ),
        disclaimer=(
            DEFAULT_DISCLAIMER_RU if locale == "ru" else DEFAULT_DISCLAIMER_EN
        ),
        ai_metadata=CopilotMetadata(
            generated=False,
            fallback_used=True,
            provider=None,
            model=None,
            fallback_reason=fallback_reason,
        ),
    )


def _build_demo_fallback_answer(
    facts: Optional[AuthoritativeCopilotFacts],
    locale: str,
    fallback_reason: str,
    analysis: Optional[WithdrawalAnalysis] = None,
    purchase_analysis: Optional[dict[str, Any]] = None,
    availability_question: bool = False,
) -> CopilotAnswer:
    """Build a deterministic fallback answer when the provider is unavailable."""
    if availability_question:
        if purchase_analysis is None:
            purchase_analysis = asdict(evaluate_demo_purchase_affordability())
        return _build_demo_available_funds_fallback_answer(
            facts, locale, fallback_reason, purchase_analysis
        )

    if purchase_analysis is not None:
        return _build_demo_purchase_fallback_answer(
            locale, fallback_reason, purchase_analysis
        )

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
    reserve_delta = ctx.reserve_saved - ctx.reserve_target
    surplus_after_bills = ctx.reserve_saved - ctx.upcoming_bills_unpaid_total
    planning_headroom = surplus_after_bills - ctx.reserve_target

    # The progress indicator is intentionally capped at 100%, but a text
    # summary must not label a larger surplus/target ratio as exactly 100%.
    if reserve_delta > 0:
        reserve_status_en = f"surplus exceeds the target by {reserve_delta} KZT"
        reserve_status_ru = f"остаток превышает целевой резерв на {reserve_delta} ₸"
    elif reserve_delta < 0:
        reserve_status_en = f"surplus is {abs(reserve_delta)} KZT below the target"
        reserve_status_ru = f"остаток ниже целевого резерва на {abs(reserve_delta)} ₸"
    else:
        reserve_status_en = "surplus exactly meets the target"
        reserve_status_ru = "остаток в точности достигает целевого резерва"

    if planning_headroom >= 0:
        bill_impact_en = (
            f"After {ctx.upcoming_bills_unpaid_total} KZT in unpaid upcoming bills, "
            f"the calculated remainder is {surplus_after_bills} KZT; "
            f"after setting aside the {ctx.reserve_target} KZT reserve target, "
            f"planning headroom is {planning_headroom} KZT."
        )
        bill_impact_ru = (
            f"После учета обязательных платежей на {ctx.upcoming_bills_unpaid_total} ₸ "
            f"расчетный остаток составляет {surplus_after_bills} ₸; "
            f"после выделения целевого резерва {ctx.reserve_target} ₸ "
            f"планируемый запас составляет {planning_headroom} ₸."
        )
    else:
        bill_impact_en = (
            f"After {ctx.upcoming_bills_unpaid_total} KZT in unpaid upcoming bills, "
            f"the calculated remainder is {surplus_after_bills} KZT, "
            f"which is {abs(planning_headroom)} KZT below the reserve target."
        )
        bill_impact_ru = (
            f"После учета обязательных платежей на {ctx.upcoming_bills_unpaid_total} ₸ "
            f"расчетный остаток составляет {surplus_after_bills} ₸, "
            f"что на {abs(planning_headroom)} ₸ ниже целевого резерва."
        )

    # --- Lead with the answer (system prompt §1) ---
    # State the actual difference from the target, not the capped UI progress.
    if locale == "ru":
        lead = (
            f"Финансовый обзор: за период заработано **{facts.earned_amount_minor // 100} ₸**, "
            f"потрачено **{ctx.expense_amount} ₸**, остаток периода — **{ctx.reserve_saved} ₸**. "
            f"Целевой резерв — **{ctx.reserve_target} ₸**; {reserve_status_ru}."
        )
    else:
        lead = (
            f"Financial overview: earned this period **{facts.earned_amount_minor // 100} KZT**, "
            f"expenses **{ctx.expense_amount} KZT**, period surplus **{ctx.reserve_saved} KZT**. "
            f"Reserve target is **{ctx.reserve_target} KZT**; {reserve_status_en}."
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
            f"EWA (Earned Wage Access) — возможность получить часть заработанной зарплаты до дня выплаты. "
            f"Политику EWA настраивает работодатель. Для вашего работодателя она пока не настроена, "
            f"поэтому досрочное получение зарплаты недоступно. "
            f"Доступная сумма EWA сейчас — **{ewa_available_kzt} ₸**. "
            f"Это доступ к досрочной выплате, а не баланс банковского счета."
        )
    else:
        ewa_edu = (
            f"EWA (Earned Wage Access) lets employees access part of their earned wages before payday. "
            f"Your employer has not configured an EWA policy, so early wage access is unavailable. "
            f"The available EWA amount is **{ewa_available_kzt} KZT**. "
            f"This is an early-access limit, not your bank-account balance."
        )
    parts.append(ewa_edu)

# Recommendations (system prompt §5: 2-3 specific, actionable recommendations)
    if locale == "ru":
        rec1 = (
            "1. Уточните у HR или payroll-администратора работодателя, планируется ли "
            "настройка EWA-политики. Пока она не настроена, досрочное получение зарплаты недоступно."
        )
        rec2 = (
            f"2. Остаток периода — это расчетная разница доходов и расходов, "
            f"а не подтвержденные накопления. Фактический баланс банковского счета неизвестен."
        )
        rec3 = (
            f"3. {bill_impact_ru} Это расчет по данным демо-профиля, "
            f"а не подтверждение наличия денег на счете."
        )
    else:
        rec1 = (
            "1. Ask your employer's HR or payroll administrator whether an EWA policy "
            "will be configured. Until then, early wage access is unavailable."
        )
        rec2 = (
            "2. The period surplus is a calculated difference between earnings and expenses, "
            "not confirmed savings. The actual bank balance is unknown."
        )
        rec3 = (
            f"3. {bill_impact_en} This is a demo-profile cash-flow calculation, "
            f"not confirmation that the money is in your account."
        )
    parts.append(rec1)
    parts.append(rec2)
    parts.append(rec3)

    # --- Limitation (system prompt §2: status/limitation section) ---
    if locale == "ru":
        parts.append(
            f"Ограничение: достижение целевого резерва рассчитано по остатку периода "
            f"и не подтверждает фактические накопления или баланс банковского счета."
        )
    else:
        parts.append(
            "Limitation: reserve-target coverage is calculated from period surplus; "
            "it does not confirm actual savings or a bank-account balance."
        )

    # --- Key facts (system prompt §3: keep tables independent, one per heading) ---
    key_facts = [
        CopilotFact(
            code="available_amount",
            text=(
                f"Доступная сумма EWA: {ewa_available_kzt} ₸; работодатель не настроил EWA-политику."
                if locale == "ru"
                else f"Available EWA amount: {ewa_available_kzt} KZT; employer EWA policy is not configured."
            ),
        ),
        CopilotFact(
            code="earned_amount",
            text=(
                f"Заработано: {facts.earned_amount_minor // 100} ₸."
                if locale == "ru"
                else f"Earned: {facts.earned_amount_minor // 100} KZT."
            ),
        ),
        CopilotFact(
            code="reserve_target",
            text=(
                f"Целевой резерв: {ctx.reserve_target} ₸, остаток за период: {ctx.reserve_saved} ₸."
                if locale == "ru"
                else f"Reserve target: {ctx.reserve_target} KZT, period surplus: {ctx.reserve_saved} KZT."
            ),
        ),
        CopilotFact(
            code="days_to_payday",
            text=(
                f"Дней до зарплаты: {ctx.days_to_payday}."
                if locale == "ru"
                else f"Days to payday: {ctx.days_to_payday}."
            ),
        ),
    ]

    return CopilotAnswer(
        response="\n\n".join(parts),
        key_facts=key_facts,
        data_limitations=[
            "Reserve-target coverage is calculated from period surplus, not confirmed savings.",
            "EWA is unavailable because the employer policy is not configured.",
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

    # Withdrawal and purchase affordability are separate server-side scenarios.
    analysis: Optional[WithdrawalAnalysis] = None
    purchase_analysis: Optional[dict[str, Any]] = None
    amount_minor = extract_hypothetical_amount_minor(message)
    purchase_affordability_question = is_purchase_affordability_question(message)
    availability_question = _is_available_funds_question(message)

    if amount_minor is not None and is_withdrawal_question(message):
        ctx = build_demo_financial_context()
        affordability = evaluate_demo_affordability(amount_minor // 100)
        analysis = _build_demo_affordability_analysis(amount_minor // 100, affordability, ctx)
        facts = _build_demo_authoritative_facts(locale, analysis=analysis)
    elif (
        purchase_affordability_question or availability_question
    ) and not is_withdrawal_question(message):
        purchase_analysis = asdict(
            evaluate_demo_purchase_affordability(
                amount_minor if purchase_affordability_question else None
            )
        )

    # Direct affordability questions with a supplied price do not need mock
    # catalogue offers. Keep product lookup for explicit shopping searches.
    product_search_results = []
    if is_shopping_query(message) and not (
        amount_minor is not None and purchase_affordability_question
    ):
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
        purchase_analysis=purchase_analysis,
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
        purchase_analysis=purchase_analysis,
    )

    # Override locale-specific fields that `generate_copilot_answer` sets to
    # English defaults (disclaimer, suggested questions).
    disclaimer = DEFAULT_DISCLAIMER_RU if locale == "ru" else DEFAULT_DISCLAIMER_EN
    suggested = DEFAULT_SUGGESTED_QUESTIONS_RU if locale == "ru" else DEFAULT_SUGGESTED_QUESTIONS_EN

    # Build a locale-aware fallback answer when the provider was unavailable.
    if answer.ai_metadata.fallback_used:
        fallback_answer = _build_demo_fallback_answer(
            facts,
            locale,
            answer.ai_metadata.fallback_reason or FALLBACK_HTTP_ERROR,
            analysis,
            purchase_analysis,
            availability_question=availability_question,
        )
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
