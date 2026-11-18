"""Regression tests for server-side demo purchase affordability."""

from __future__ import annotations

from dataclasses import asdict
import unittest

from app.api.v1.demo_ai import (
    _build_demo_authoritative_facts,
    _build_demo_fallback_answer,
    demo_chat_endpoint,
)
from app.core.rate_limit import get_provider_limiter
from app.schemas.ai import ChatRequest
from app.services.ai_copilot import (
    FALLBACK_NOT_CONFIGURED,
    FakeCopilotProvider,
    authoritative_numeric_values,
    find_unsupported_amount,
    sanitize_provider_payload,
)
from app.services.demo_financial_context import (
    build_demo_sanitized_input,
    evaluate_demo_purchase_affordability,
)


class DemoPurchaseAffordabilityCalculationTests(unittest.TestCase):
    def test_macbook_price_uses_period_flow_bills_and_reserve(self) -> None:
        result = evaluate_demo_purchase_affordability(50_000_000)

        self.assertEqual(result.purchase_amount_minor, 50_000_000)
        self.assertEqual(result.period_surplus_minor, 13_180_000)
        self.assertEqual(result.upcoming_bills_unpaid_minor, 5_740_000)
        self.assertEqual(result.amount_after_bills_minor, 7_440_000)
        self.assertEqual(result.reserve_target_minor, 6_000_000)
        self.assertEqual(result.purchase_headroom_minor, 1_440_000)
        self.assertEqual(result.shortfall_minor, 48_560_000)
        self.assertEqual(
            result.remaining_after_purchase_and_bills_minor, -42_560_000
        )
        self.assertFalse(result.fits_period_buffer)
        self.assertFalse(result.bank_balance_confirmed)

    def test_purchase_at_exact_headroom_fits_period_buffer(self) -> None:
        result = evaluate_demo_purchase_affordability(1_440_000)

        self.assertTrue(result.fits_period_buffer)
        self.assertEqual(result.shortfall_minor, 0)

    def test_purchase_headroom_is_available_without_a_price(self) -> None:
        result = evaluate_demo_purchase_affordability()

        self.assertIsNone(result.purchase_amount_minor)
        self.assertEqual(result.purchase_headroom_minor, 1_440_000)
        self.assertIsNone(result.fits_period_buffer)
        self.assertIsNone(result.shortfall_minor)

    def test_invalid_purchase_amount_is_rejected(self) -> None:
        for amount in (0, -100, True, 1.5):
            with self.subTest(amount=amount):
                with self.assertRaises(ValueError):
                    evaluate_demo_purchase_affordability(amount)  # type: ignore[arg-type]

    def test_purchase_values_are_allowlisted_for_provider_output(self) -> None:
        analysis = asdict(evaluate_demo_purchase_affordability(50_000_000))
        payload = sanitize_provider_payload(
            build_demo_sanitized_input(purchase_analysis=analysis)
        )
        self.assertEqual(payload["purchase_analysis"], analysis)

        allowed = authoritative_numeric_values(
            _build_demo_authoritative_facts("en"),
            additional_facts=analysis,
        )
        for amount in (
            "500,000 KZT",
            "131,800 KZT",
            "57,400 KZT",
            "74,400 KZT",
            "60,000 KZT",
            "14,400 KZT",
            "485,600 KZT",
        ):
            with self.subTest(amount=amount):
                self.assertIsNone(find_unsupported_amount(amount, allowed))


class DemoPurchaseAffordabilityChatTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        get_provider_limiter().reset()

    async def asyncTearDown(self) -> None:
        get_provider_limiter().reset()

    async def test_demo_chat_passes_server_purchase_analysis_to_ai(self) -> None:
        provider = FakeCopilotProvider(
            response={
                "response": (
                    "No, not from the demo period-flow buffer alone: a 500,000 KZT "
                    "purchase exceeds the 14,400 KZT headroom after unpaid bills and "
                    "the 60,000 KZT reserve by 485,600 KZT. The 131,800 KZT period "
                    "surplus minus 57,400 KZT in bills leaves 74,400 KZT. Actual "
                    "bank savings are unknown."
                ),
                "key_facts": [],
                "data_limitations": [
                    "Actual bank balance and savings are not confirmed."
                ],
                "suggested_questions": [],
            }
        )

        response = await demo_chat_endpoint(
            ChatRequest(message="Can I afford to buy a MacBook for 500,000 KZT?"),
            provider,
            None,
        )

        self.assertTrue(response.ai_metadata.generated)
        self.assertFalse(response.ai_metadata.fallback_used)
        self.assertIn("purchase_analysis", provider.last_payload)
        self.assertEqual(
            provider.last_payload["purchase_analysis"]["purchase_amount_minor"],
            50_000_000,
        )
        self.assertEqual(
            provider.last_payload["purchase_analysis"]["purchase_headroom_minor"],
            1_440_000,
        )
        self.assertIn("500,000 KZT", response.response)

    def test_purchase_fallback_avoids_unrelated_ewa_information(self) -> None:
        analysis = asdict(evaluate_demo_purchase_affordability(50_000_000))
        response = _build_demo_fallback_answer(
            _build_demo_authoritative_facts("en"),
            "en",
            FALLBACK_NOT_CONFIGURED,
            purchase_analysis=analysis,
        )

        self.assertIn("500,000 KZT", response.response)
        self.assertIn("485,600 KZT", response.response)
        self.assertIn("14,400 KZT", response.response)
        self.assertIn(
            "bank balance and savings are unknown",
            response.data_limitations[0],
        )
        self.assertNotIn("EWA", response.response)


if __name__ == "__main__":
    unittest.main()
