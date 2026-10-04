"""Phase 3.3 — Structured AI Decision Layer.

This module implements the interpretation/explanation layer that sits ON TOP of
the deterministic Phase 2 + Phase 3.1 + Phase 3.2 pipeline.

Trust boundary (NON-NEGOTIABLE):
    The LLM never calculates or decides financial state. All authoritative
    numbers (requestable, blocking reasons, balances, limits, withdrawal
    counts, budget totals) are read from Phase 3.2 `WithdrawalAnalysis` and
    placed in the server-constructed `WithdrawalDecisionResponse`. The LLM-
    owned schema (`DecisionContent`) contains ONLY prose/code explanations and
    has no numerical authority.

The only thing this module adds over Phase 3.2 is human-readable explanation.
If the provider is unavailable, malformed, or absent from config, a fully
deterministic fallback is used so financial analysis remains available.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from datetime import date
from typing import Any, Optional

from openai import AsyncOpenAI
from openai import APIStatusError
from openai import APITimeoutError
from openai import APIConnectionError
from openai import RateLimitError

from app.config import get_settings
from app.schemas.ai_decision import (
    AIMetadata,
    DecisionContent,
    DecisionConsideration,
    DecisionFact,
    DecisionOption,
    StructuredDecision,
    WithdrawalDecisionResponse,
)
from app.services.financial_context_service import (
    analyze_withdrawal_from_context,
    build_financial_context,
)

logger = logging.getLogger("arqau.ai_decision")

# Reuses the existing 30s precedent from the legacy ai_service.
AI_TIMEOUT_SECONDS = 30.0

DEFAULT_DISCLAIMER = (
    "This is illustrative guidance, not financial advice. ARQAU does not "
    "guarantee any specific financial outcome."
)

# Server-owned mapping from Phase 3.2 blocking codes to explanation text.
_BLOCKING_EXPLANATIONS = {
    "EWA_NOT_ELIGIBLE": "Current EWA eligibility conditions are not met for this user.",
    "WITHDRAWAL_NOT_ALLOWED": "The current EWA state does not permit a withdrawal request at this time.",
    "AMOUNT_BELOW_MINIMUM": "The requested amount is below the configured minimum withdrawal.",
    "AMOUNT_EXCEEDS_MAX_REQUESTABLE": "The requested amount exceeds the current deterministic maximum requestable.",
    "WITHDRAWAL_LIMIT_REACHED": "The withdrawal-count limit for this period has been reached.",
}


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are ARQAU's financial decision-explanation assistant.

Your ONLY job is to EXPLAIN deterministic backend facts. You do NOT decide,
calculate, or authorize anything.

Rules:
1. All financial numbers below are supplied by the backend and are
   authoritative. Do NOT invent, estimate, or guess any financial figure.
2. Do NOT contradict requestable or blocking_reasons.
3. Do NOT invent budget, spending, goal, income, or EWA data when it is
   absent. Acknowledge when data is unavailable.
4. Do NOT claim the user will spend the money in any particular way.
5. Do NOT claim an EWA withdrawal is an expense or obligation.
6. Do NOT guarantee that a later withdrawal request will succeed.
7. Do NOT provide legal, tax, or investment advice.
8. Do NOT use subjective labels (safe/dangerous/good/bad/smart/stupid).
9. Do NOT invent a numeric risk score.
10. Provide neutral, grounded next-step options only.
11. Keep explanations concise and concrete.
12. Acknowledge missing information rather than speculating.

Return ONLY a JSON object matching the requested schema; no prose outside it.
"""


def build_decision_messages(payload: dict[str, Any]) -> list[dict[str, str]]:
    """Build the allow-listed fact payload and the LLM messages.

    The payload is the sanitized provider input (see `build_sanitized_input`):
    it contains only aggregate financial facts — never raw transactions,
    goals, identity, tokens, or internal IDs.
    """
    facts = json.dumps(payload, default=str, ensure_ascii=False)
    user = (
        "Explain the following deterministic withdrawal analysis. You may only "
        "interpret these facts; you must not calculate, change, or override any "
        "of them. Acknowledge any unavailable data. Provide only neutral, "
        "next-step options grounded in the facts. Return ONLY a JSON object "
        "matching the requested schema; do not add prose outside it.\n\n"
        f"Deterministic facts:\n{facts}"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


# ---------------------------------------------------------------------------
# Provider abstraction
# ---------------------------------------------------------------------------


class DecisionAIProvider(ABC):
    """Abstract provider boundary so tests can substitute a deterministic fake."""

    @property
    def name(self) -> Optional[str]:
        return None

    @property
    def model(self) -> Optional[str]:
        return None

    @abstractmethod
    async def generate_decision(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Return the provider's raw (unvalidated) decision dict."""
        raise NotImplementedError


class OpenAIDecisionProvider(DecisionAIProvider):
    """Production provider backed by the existing OpenAI/OpenRouter config.

    Reuses `app.config.get_settings` for API key, model, and the 30s timeout
    precedent. Does NOT reuse the legacy unsafe prompt/calculation logic in
    `ai_service.build_withdrawal_prompt` / `ai_service.analyze_withdrawal`.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: float = AI_TIMEOUT_SECONDS,
    ) -> None:
        self._api_key = api_key or ""
        self._model = model
        self._timeout = timeout
        self._client: Optional[AsyncOpenAI] = None

    @property
    def name(self) -> Optional[str]:
        if self._api_key.startswith("sk-or-"):
            return "openrouter"
        return "openai" if self._api_key else None

    @property
    def model(self) -> Optional[str]:
        return self._model or None

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            api_key = self._api_key
            client_kwargs: dict[str, Any] = {"api_key": api_key, "timeout": self._timeout}
            if api_key.startswith("sk-or-"):
                client_kwargs["base_url"] = "https://openrouter.ai/api/v1"
            self._client = AsyncOpenAI(**client_kwargs)
        return self._client

    async def generate_decision(self, payload: dict[str, Any]) -> dict[str, Any]:
        client = self._get_client()
        schema = DecisionContent.model_json_schema()
        schema["additionalProperties"] = False
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": "StructuredDecision",
                "schema": schema,
                "strict": False,
            },
        }
        messages = build_decision_messages(payload)
        completion = await client.chat.completions.create(
            model=self._model,
            messages=messages,
            response_format=response_format,
            max_tokens=800,
            temperature=0.3,
            timeout=self._timeout,
        )
        content = completion.choices[0].message.content or ""
        return json.loads(content)


class FakeDecisionProvider(DecisionAIProvider):
    """Deterministic test provider. Captures the payload it receives and
    returns a canned (or failing) response."""

    def __init__(
        self,
        response: Optional[dict[str, Any]] = None,
        exc: Optional[BaseException] = None,
    ) -> None:
        self._response = response
        self._exc = exc
        self.last_payload: Optional[dict[str, Any]] = None
        self.call_count: int = 0

    @property
    def name(self) -> Optional[str]:
        return "fake"

    @property
    def model(self) -> Optional[str]:
        return "fake-model"

    async def generate_decision(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.last_payload = payload
        self.call_count += 1
        if self._exc is not None:
            raise self._exc
        if self._response is None:
            raise APITimeoutError("no-response-configured")
        # Return a shallow copy so callers can't mutate our canned response.
        return json.loads(json.dumps(self._response))


def _build_production_provider() -> DecisionAIProvider:
    settings = get_settings()
    return OpenAIDecisionProvider(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        timeout=AI_TIMEOUT_SECONDS,
    )


_PRODUCTION_PROVIDER: Optional[DecisionAIProvider] = None


def get_decision_provider() -> DecisionAIProvider:
    """FastAPI dependency. Tests override via `app.dependency_overrides`."""
    global _PRODUCTION_PROVIDER
    if _PRODUCTION_PROVIDER is None:
        _PRODUCTION_PROVIDER = _build_production_provider()
    return _PRODUCTION_PROVIDER


def reset_production_provider() -> None:
    global _PRODUCTION_PROVIDER
    _PRODUCTION_PROVIDER = None


# ---------------------------------------------------------------------------
# Sanitized AI input
# ---------------------------------------------------------------------------

# Fields the provider is permitted to see. Everything else (identity, tokens,
# internal IDs, raw transaction/goal rows, ORM objects) is excluded.
_ALLOWED_INPUT_FIELDS = (
    "requested_amount_minor",
    "requestable",
    "blocking_reasons",
    "earned_amount_minor",
    "available_amount_minor",
    "max_requestable_amount_minor",
    "requested_share_of_earned_bps",
    "requested_share_of_policy_limit_bps",
    "exposure_before_minor",
    "exposure_after_minor",
    "withdrawals_this_period",
    "max_withdrawals_per_period",
    "budget_available",
    "budget_total_minor",
    "budget_spent_minor",
    "budget_remaining_minor",
    "has_transactions",
    "has_budget",
    "has_goals",
    "unavailable_analysis",
)


def sanitize_provider_dict(payload: dict[str, Any]) -> dict[str, Any]:
    """Project the provider input to the strict allow-list."""
    return {k: payload[k] for k in _ALLOWED_INPUT_FIELDS if k in payload}


def build_sanitized_input(
    analysis: Any,
    ctx: Any,
) -> dict[str, Any]:
    """Construct the minimal, allow-listed fact payload for the provider."""
    dq = ctx.data_quality
    budget = ctx.budget
    limitations: list[str] = []
    if not dq.has_salary_profile:
        limitations.append("salary_profile")
    if not dq.has_ewa_policy:
        limitations.append("ewa_policy")
    if not budget.available:
        limitations.append("budget")
    if not ctx.goals.available:
        limitations.append("financial_goals")

    raw = {
        "requested_amount_minor": analysis.requested_amount_minor,
        "requestable": analysis.requestability.requestable,
        "blocking_reasons": list(analysis.requestability.blocking_reasons),
        "earned_amount_minor": analysis.current_state.earned_amount_minor,
        "available_amount_minor": analysis.current_state.available_amount_minor,
        "max_requestable_amount_minor": analysis.current_state.max_requestable_amount_minor,
        "requested_share_of_earned_bps": analysis.impact.requested_share_of_earned_bps,
        "requested_share_of_policy_limit_bps": analysis.impact.requested_share_of_policy_limit_bps,
        "exposure_before_minor": analysis.impact.exposure_before_minor,
        "exposure_after_minor": analysis.impact.exposure_after_minor,
        "withdrawals_this_period": analysis.withdrawal_frequency.withdrawals_this_period,
        "max_withdrawals_per_period": analysis.withdrawal_frequency.max_withdrawals_per_period,
        "budget_available": budget.available,
        "budget_total_minor": budget.total_budget_minor,
        "budget_spent_minor": budget.spent_minor,
        "budget_remaining_minor": budget.remaining_minor,
        "has_transactions": dq.has_transactions,
        "has_budget": dq.has_budget,
        "has_goals": dq.has_goals,
        "unavailable_analysis": limitations,
    }
    return sanitize_provider_dict(raw)


# ---------------------------------------------------------------------------
# Deterministic fallback
# ---------------------------------------------------------------------------

_FALLBACK_OPTION_CONTINUE = DecisionOption(
    code="opt_continue",
    text="Proceed with the withdrawal through the standard request flow when ready.",
)
_FALLBACK_OPTION_REVIEW_AMOUNT = DecisionOption(
    code="opt_review_amount",
    text="Review the requested amount against the displayed maximum requestable.",
)
_FALLBACK_OPTION_REVIEW_BLOCKING = DecisionOption(
    code="opt_review_blocking",
    text="Review the listed blocking conditions before retrying.",
)
_FALLBACK_OPTION_WAIT = DecisionOption(
    code="opt_wait",
    text="Wait until the pay-period or employment state changes, then re-evaluate.",
)
_FALLBACK_OPTION_REVIEW_BUDGET = DecisionOption(
    code="opt_review_budget",
    text="Review budget information before continuing, where available.",
)


def _fallback_options(analysis: Any) -> list[DecisionOption]:
    if analysis.requestability.requestable:
        return [
            _FALLBACK_OPTION_CONTINUE,
            _FALLBACK_OPTION_REVIEW_AMOUNT,
            _FALLBACK_OPTION_REVIEW_BUDGET,
        ]
    opts: list[DecisionOption] = [_FALLBACK_OPTION_REVIEW_BLOCKING]
    max_req = analysis.current_state.max_requestable_amount_minor
    if max_req is not None and max_req > 0:
        opts.append(
            DecisionOption(
                code="opt_reduce_to_max",
                text=f"Reduce the amount to the deterministic maximum of {max_req} minor.",
            )
        )
    opts.append(_FALLBACK_OPTION_WAIT)
    return opts


def build_fallback_decision(
    analysis: Any,
    provider_name: Optional[str] = None,
    provider_model: Optional[str] = None,
) -> StructuredDecision:
    """Deterministic, server-owned fallback generated only from backend facts.

    Never uses a risk score or subjective safety labels.
    """
    available = analysis.current_state.available_amount_minor
    max_req = analysis.current_state.max_requestable_amount_minor

    if analysis.requestability.requestable:
        summary = "Analysis complete; the requested amount is currently requestable."
        status_explanation = (
            f"The requested amount of {analysis.requested_amount_minor} minor is "
            f"currently requestable. Available capacity is "
            f"{available} minor and the deterministic maximum requestable is "
            f"{max_req} minor."
        )
    else:
        reason_texts = [
            _BLOCKING_EXPLANATIONS.get(r, r)
            for r in analysis.requestability.blocking_reasons
        ] or ["The withdrawal cannot currently be processed."]
        summary = "Analysis complete; the requested amount is not currently requestable."
        status_explanation = " ".join(reason_texts)

    key_facts: list[DecisionFact] = []
    for reason in analysis.requestability.blocking_reasons:
        key_facts.append(
            DecisionFact(
                code=reason,
                text=_BLOCKING_EXPLANATIONS.get(reason, reason),
            )
        )
    if available is not None:
        key_facts.append(
            DecisionFact(
                code="available_amount",
                text=f"Current available EWA capacity: {available} minor.",
            )
        )
    if max_req is not None:
        key_facts.append(
            DecisionFact(
                code="max_requestable",
                text=f"Current deterministic maximum requestable: {max_req} minor.",
            )
        )

    considerations: list[DecisionConsideration] = []
    if analysis.requestability.blocking_reasons:
        considerations.append(
            DecisionConsideration(
                code="blocking_present",
                text="One or more deterministic blocking conditions apply; see key_facts.",
            )
        )
    else:
        considerations.append(
            DecisionConsideration(
                code="no_blocks",
                text="No deterministic blocking conditions apply to this amount.",
            )
        )
    if analysis.data_quality.unavailable_analysis is not None:
        considerations.append(
            DecisionConsideration(
                code="analysis_unavailable",
                text=str(analysis.data_quality.unavailable_analysis),
            )
        )

    data_limitations: list[str] = []
    if not analysis.data_quality.has_budget:
        data_limitations.append("Budget data is unavailable; budget impact cannot be evaluated.")
    if not analysis.data_quality.has_transactions:
        data_limitations.append("Transaction data is unavailable; spending impact cannot be evaluated.")
    if not analysis.data_quality.has_goals:
        data_limitations.append("Goal data is unavailable; goal impact cannot be evaluated.")

    return StructuredDecision(
        summary=summary,
        status_explanation=status_explanation,
        key_facts=key_facts,
        considerations=considerations,
        options=_fallback_options(analysis),
        data_limitations=data_limitations,
        disclaimer=DEFAULT_DISCLAIMER,
        ai_metadata=AIMetadata(
            generated=False,
            fallback_used=True,
            provider=provider_name,
            model=provider_model,
        ),
    )


# ---------------------------------------------------------------------------
# Decision orchestration
# ---------------------------------------------------------------------------


async def generate_decision(
    provider: DecisionAIProvider,
    payload: dict[str, Any],
    analysis: Any,
) -> StructuredDecision:
    """Run the provider and validate its output; fall back deterministically.

    Never trusts provider output to set authoritative financial state. A
    provider failure or schema violation yields a server-owned fallback.
    """
    provider_name = provider.name
    provider_model = provider.model

    try:
        raw = await provider.generate_decision(payload)
    except APITimeoutError as exc:
        logger.warning("AI decision timed out: %s", str(exc)[:200])
        return build_fallback_decision(analysis, provider_name, provider_model)
    except (APIConnectionError, RateLimitError, APIStatusError) as exc:
        status = getattr(exc, "status_code", None)
        logger.warning(
            "AI decision provider error: type=%s status=%s detail=%s",
            type(exc).__name__,
            status,
            str(exc)[:200],
        )
        return build_fallback_decision(analysis, provider_name, provider_model)
    except Exception as exc:  # noqa: BLE001 - any provider failure -> fallback
        logger.warning("AI decision unexpected error: %s=%s", type(exc).__name__, str(exc)[:200])
        return build_fallback_decision(analysis, provider_name, provider_model)

    if not isinstance(raw, dict):
        logger.warning("AI decision returned non-dict payload; using fallback.")
        return build_fallback_decision(analysis, provider_name, provider_model)

    try:
        content = DecisionContent.model_validate(raw)
    except Exception:  # noqa: BLE001 - schema violation -> fallback
        logger.warning("AI decision failed schema validation; using fallback.")
        return build_fallback_decision(analysis, provider_name, provider_model)

    return StructuredDecision(
        summary=content.summary,
        status_explanation=content.status_explanation,
        key_facts=content.key_facts,
        considerations=content.considerations,
        options=content.options,
        data_limitations=content.data_limitations,
        disclaimer=content.disclaimer,
        ai_metadata=AIMetadata(
            generated=True,
            fallback_used=False,
            provider=provider_name,
            model=provider_model,
        ),
    )


async def make_withdrawal_decision(
    db: Any,
    user: Any,
    amount_minor: int,
    calculation_date: Optional[date] = None,
    provider: Optional[DecisionAIProvider] = None,
) -> WithdrawalDecisionResponse:
    """Authoritative entry point for POST /financial/withdrawal-decision.

    Build the deterministic Phase 3.1/3.2 context once, run the Phase 3.2
    analysis (authoritative), sanitize the input for the provider, obtain an
    AI explanation (or deterministic fallback), and assemble the response
    envelope with authoritative fields taken ONLY from Phase 3.2.

    Read-only: creates no WageAccessRequest and mutates no financial state.
    """
    if provider is None:
        provider = get_decision_provider()

    ctx = await build_financial_context(db, user, calculation_date)
    analysis = analyze_withdrawal_from_context(ctx, amount_minor)
    payload = build_sanitized_input(analysis, ctx)
    decision = await generate_decision(provider, payload, analysis)

    return WithdrawalDecisionResponse(
        requested_amount_minor=analysis.requested_amount_minor,
        requestable=analysis.requestability.requestable,
        blocking_reasons=list(analysis.requestability.blocking_reasons),
        current_available_amount_minor=analysis.current_state.available_amount_minor,
        max_requestable_amount_minor=analysis.current_state.max_requestable_amount_minor,
        snapshot_only=True,
        decision=decision,
    )
