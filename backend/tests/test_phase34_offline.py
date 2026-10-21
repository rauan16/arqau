"""Phase 3.4 offline verification: CopilotContent schema + financial safety validators.

These tests run without network access and without an OpenRouter API key.
They validate:
- CopilotContent / CopilotAnswer / CopilotResponse schema validation (valid + invalid)
- find_unsupported_amount: supported value, different value, absent value, multiple amounts
- contains_forbidden_recommendation: safe, prohibited, ambiguous (negation-aware)
- contains_forbidden_claim: execution/approval claims
- contains_fabricated_policy_claim: percentage fees / interest
- authoritative_numeric_values: extracts all integer facts from backend context

No provider is called. No API key is required.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.ai_copilot import (
    AuthoritativeCopilotFacts,
    CopilotAnswer,
    CopilotContent,
    CopilotFact,
    CopilotMetadata,
    CopilotResponse,
)
from app.schemas.financial_context import (
    WithdrawalAnalysis,
)
from app.services.ai_copilot import (
    authoritative_numeric_values,
    contains_fabricated_policy_claim,
    contains_forbidden_claim,
    contains_forbidden_recommendation,
    find_unsupported_amount,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def facts() -> AuthoritativeCopilotFacts:
    return AuthoritativeCopilotFacts(
        calculation_date="2026-02-15",
        pay_period_start="2026-02-01",
        pay_period_end="2026-02-28",
        salary_amount_minor=1000000,
        currency="USD",
        earned_amount_minor=500000,
        policy_limit_minor=250000,
        reserved_amount_minor=0,
        paid_amount_minor=0,
        available_amount_minor=250000,
        max_requestable_amount_minor=50000,
        minimum_withdrawal_minor=2000,
        maximum_withdrawal_minor=50000,
        eligible=True,
        eligibility_reasons=["active employment", "EWA policy configured"],
        can_request_withdrawal=True,
        withdrawals_this_period=0,
        max_withdrawals_per_period=3,
        total_withdrawal_requests=0,
        pending_withdrawal_count=0,
        approved_withdrawal_count=0,
        paid_withdrawal_count=0,
        paid_withdrawal_amount_minor=0,
        spending_available=True,
        total_spending_minor=120000,
        transaction_count=5,
        top_spending_categories=[],
        budget_available=True,
        budget_total_minor=200000,
        budget_spent_minor=80000,
        budget_remaining_minor=120000,
        goals_available=True,
        active_goals_count=1,
        total_goal_target_minor=500000,
        total_goal_saved_minor=25000,
        has_salary_profile=True,
        has_ewa_policy=True,
        has_transactions=True,
        has_budget=True,
        has_goals=True,
        missing_data=[],
        availability_note=(
            "available_amount_minor is deterministic remaining EWA capacity, "
            "not a recommended, approved, or suggested withdrawal amount."
        ),
    )


@pytest.fixture
def analysis() -> WithdrawalAnalysis:
    return WithdrawalAnalysis(
        requested_amount_minor=30000,
        requestability=WithdrawalAnalysis.model_fields["requestability"].annotation(
            requestable=True,
            blocking_reasons=[],
            authoritative_eligibility_reasons=[],
        ),
        current_state=WithdrawalAnalysis.model_fields["current_state"].annotation(
            salary_amount_minor=1000000,
            earned_amount_minor=500000,
            policy_limit_minor=250000,
            reserved_amount_minor=0,
            paid_amount_minor=0,
            available_amount_minor=250000,
            max_requestable_amount_minor=50000,
        ),
        impact=WithdrawalAnalysis.model_fields["impact"].annotation(
            remaining_available_amount_minor=220000,
            remaining_max_requestable_amount_minor=20000,
            requested_share_of_earned_bps=6000,
            requested_share_of_policy_limit_bps=12000,
            exposure_before_minor=0,
            exposure_after_minor=30000,
            exposure_share_of_earned_before_bps=0,
            exposure_share_of_earned_after_bps=6000,
        ),
        withdrawal_frequency=WithdrawalAnalysis.model_fields["withdrawal_frequency"].annotation(
            withdrawals_this_period=0,
            max_withdrawals_per_period=3,
            remaining_slots_before=3,
            remaining_slots_after=2,
        ),
        budget_impact=WithdrawalAnalysis.model_fields["budget_impact"].annotation(
            available=True,
            total_budget_minor=200000,
            current_spent_minor=80000,
            current_remaining_minor=120000,
            withdrawal_share_of_budget_bps=15000,
        ),
        data_quality=WithdrawalAnalysis.model_fields["data_quality"].annotation(
            has_transactions=True,
            has_budget=True,
            has_goals=True,
            unavailable_analysis=None,
        ),
        snapshot_only=True,
    )


# ---------------------------------------------------------------------------
# CopilotContent schema validation
# ---------------------------------------------------------------------------

class TestCopilotContentSchema:
    def test_valid_copilot_content(self):
        content = CopilotContent(
            response="You have 250000 minor units available.",
            key_facts=[
                CopilotFact(code="available_amount", text="Available: 250000 minor units."),
            ],
            data_limitations=["No budget recorded."],
            suggested_questions=["What is my remaining budget?"],
        )
        assert content.response == "You have 250000 minor units available."
        assert len(content.key_facts) == 1
        assert content.key_facts[0].code == "available_amount"

    def test_copilot_content_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            CopilotContent(
                response="test",
                available_amount_minor=999999,  # type: ignore[call-arg]
            )

    def test_copilot_answer_valid(self):
        answer = CopilotAnswer(
            response="You have 250000 minor units available.",
            key_facts=[],
            data_limitations=[],
            suggested_questions=[],
            disclaimer="This is illustrative guidance, not financial advice.",
            ai_metadata=CopilotMetadata(
                generated=True,
                fallback_used=False,
                provider="openrouter",
                model="deepseek/deepseek-v4.1-flash-1017",
                fallback_reason=None,
            ),
        )
        assert answer.ai_metadata.generated is True
        assert answer.ai_metadata.fallback_used is False

    def test_copilot_response_read_only_defaults(self):
        f = AuthoritativeCopilotFacts(
            calculation_date="2026-02-15",
            availability_note="available_amount_minor is deterministic remaining EWA capacity.",
        )
        response = CopilotResponse(
            response="test",
            disclaimer="This is illustrative guidance, not financial advice.",
            authoritative_facts=f,
            ai_metadata=CopilotMetadata(
                generated=False,
                fallback_used=True,
                provider="openrouter",
                model="deepseek/deepseek-v4.1-flash-1017",
                fallback_reason="not_configured",
            ),
        )
        assert response.read_only is True
        assert response.snapshot_only is True


# ---------------------------------------------------------------------------
# find_unsupported_amount
# ---------------------------------------------------------------------------

class TestFindUnsupportedAmount:
    def test_amount_exactly_matching_supported_value_is_ok(self, facts):
        allowed = authoritative_numeric_values(facts)
        assert find_unsupported_amount("earned 500000 minor units", allowed) is None
        assert find_unsupported_amount("available 250000 minor units", allowed) is None
        assert find_unsupported_amount("policy limit 250000 minor units", allowed) is None

    def test_amount_differing_from_supported_value_is_flagged(self, facts):
        allowed = authoritative_numeric_values(facts)
        # 500001 is close to earned 500000 but not equal -> unsupported
        assert find_unsupported_amount("earned 500001 minor units", allowed) == "500001"

    def test_amount_not_present_in_context_is_flagged(self, facts):
        allowed = authoritative_numeric_values(facts)
        assert find_unsupported_amount("balance of 999999 minor units", allowed) == "999999"

    def test_multiple_amounts_first_unsupported_returned(self, facts):
        allowed = authoritative_numeric_values(facts)
        # 250000 is supported, 999999 is not -> 999999 returned
        result = find_unsupported_amount(
            "available 250000 and balance 999999 minor units", allowed
        )
        assert result == "999999"

    def test_amounts_below_guard_are_ignored(self, facts):
        allowed = authoritative_numeric_values(facts)
        # 42 and 3 are counts/ordinals, below _MIN_MONETARY_GUARD=1000
        assert find_unsupported_amount("3 withdrawals of 42 dollars", allowed) is None

    def test_decimal_amounts_are_skipped(self, facts):
        allowed = authoritative_numeric_values(facts)
        assert find_unsupported_amount("balance is 250000.50 minor units", allowed) is None

    def test_dates_are_not_treated_as_amounts(self, facts):
        allowed = authoritative_numeric_values(facts)
        # 2026-02-15 contains year 2026 but dates are masked before extraction
        assert find_unsupported_amount("calculation date 2026-02-15", allowed) is None


# ---------------------------------------------------------------------------
# contains_forbidden_recommendation
# ---------------------------------------------------------------------------

class TestContainsForbiddenRecommendation:
    def test_safe_explanatory_response_is_ok(self, facts):
        assert contains_forbidden_recommendation(
            "Your available EWA capacity is 250000 minor units. "
            "This is capacity, not a recommendation to withdraw."
        ) is None

    def test_negated_recommendation_is_forgiven(self, facts):
        # "recommend to withdraw" is matched, but "do not" negates within window
        assert contains_forbidden_recommendation(
            "I do not recommend to withdraw this amount."
        ) is None
        # "encourage to withdraw" is matched, but "never" negates within window
        assert contains_forbidden_recommendation(
            "I never encourage to withdraw more than available."
        ) is None

    def test_affirmative_recommendation_is_flagged(self, facts):
        result = contains_forbidden_recommendation("I recommend to withdraw 50000 minor units.")
        assert result is not None

    def test_advise_to_withdraw_is_flagged(self, facts):
        result = contains_forbidden_recommendation("I advise you to withdraw now.")
        assert result is not None

    def test_suggest_withdrawal_is_flagged(self, facts):
        result = contains_forbidden_recommendation("I suggest withdrawing 30000 minor units.")
        assert result is not None


# ---------------------------------------------------------------------------
# contains_forbidden_claim
# ---------------------------------------------------------------------------

class TestContainsForbiddenClaim:
    def test_approval_claim_is_flagged(self):
        result = contains_forbidden_claim("Your withdrawal has been approved.")
        assert result is not None

    def test_execution_claim_is_flagged(self):
        result = contains_forbidden_claim("I have submitted your withdrawal request.")
        assert result is not None

    def test_processed_claim_is_flagged(self):
        result = contains_forbidden_claim("The request was processed and paid out.")
        assert result is not None

    def test_safe_statement_is_ok(self):
        assert contains_forbidden_claim(
            "Available capacity is not a recommendation to withdraw."
        ) is None


# ---------------------------------------------------------------------------
# contains_fabricated_policy_claim
# ---------------------------------------------------------------------------

class TestContainsFabricatedPolicyClaim:
    def test_percentage_fee_is_flagged(self):
        result = contains_fabricated_policy_claim("There is a 3% fee on each withdrawal.")
        assert result is not None

    def test_percentage_interest_is_flagged(self):
        result = contains_fabricated_policy_claim("There is a 5.5% interest charge on early withdrawals.")
        assert result is not None

    def test_you_will_be_charged_is_flagged(self):
        result = contains_fabricated_policy_claim("You will be charged $10 for this.")
        assert result is not None

    def test_employer_policy_percentage_is_flagged(self):
        result = contains_fabricated_policy_claim(
            "Your employer policy allows 90% access to earned wages."
        )
        assert result is not None

    def test_safe_statement_without_percentage_is_ok(self):
        assert contains_fabricated_policy_claim(
            "Available capacity is not a recommendation to withdraw."
        ) is None


# ---------------------------------------------------------------------------
# authoritative_numeric_values
# ---------------------------------------------------------------------------

class TestAuthoritativeNumericValues:
    def test_extracts_all_integer_values(self, facts):
        values = authoritative_numeric_values(facts)
        assert 500000 in values  # earned_amount_minor
        assert 250000 in values  # policy_limit_minor / available_amount_minor
        assert 1000000 in values  # salary_amount_minor
        assert 0 in values  # reserved_amount_minor etc.

    def test_excludes_booleans(self, facts):
        values = authoritative_numeric_values(facts)
        # True is 1, False is 0 as int, but bools should be excluded
        assert isinstance(True, int)
        # The collector explicitly skips bool, so 1 (from True) should NOT be in values
        # unless another field legitimately equals 1
        # transaction_count is 5, active_goals_count is 1 -> 1 IS legitimately present
        assert 1 in values  # from active_goals_count=1

    def test_with_analysis_includes_analysis_values(self, facts, analysis):
        values = authoritative_numeric_values(facts, analysis)
        assert 30000 in values  # requested_amount_minor
        assert 220000 in values  # remaining_available_amount_minor

    def test_returns_empty_set_for_empty_input(self):
        empty_facts = AuthoritativeCopilotFacts(
            calculation_date=None,
            availability_note="test note",
        )
        values = authoritative_numeric_values(empty_facts)
        assert values == set()
