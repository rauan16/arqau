"""Phase 2.1 Demo Safety Regression Tests

Verifies that authenticated onboarding no longer generates fake EarnedWages
from monthly_income_range.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import httpx
from sqlalchemy import text

from app.core.database import Base, configure_database, create_database
from app.config import get_settings
from app.database import get_db
from app.main import app

os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("OPENAI_API_KEY", "test-key")


class Phase21DemoSafetyTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "demo_safety.db"
        self.database_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
        self.original_url = get_settings().database_url
        self.engine, self.sessions = create_database(self.database_url)
        await configure_database(self.database_url)
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async def override_db():
            async with self.sessions() as session:
                yield session

        app.dependency_overrides[get_db] = override_db
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        )

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()
        if self.original_url:
            await configure_database(self.original_url)
        await self.engine.dispose()
        self.temp_dir.cleanup()

    async def _register_and_login(self, email: str, password: str = "password123", name: str | None = None):
        body = {"email": email, "password": password}
        if name is not None:
            body["name"] = name
        response = await self.client.post("/auth/register", json=body)
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        return data["access_token"], data["user_id"]

    # Test A: new user -> onboarding with monthly_income_range -> no EarnedWages row created
    async def test_onboarding_does_not_create_earned_wages(self) -> None:
        token, user_id = await self._register_and_login("demo_safety_a@example.com", name="User A")
        headers = {"Authorization": f"Bearer {token}"}

        # Save onboarding with monthly_income_range
        onboarding = await self.client.put(
            "/auth/onboarding",
            headers=headers,
            json={"pay_frequency": "monthly", "monthly_income_range": "150,000-300,000"},
        )
        self.assertEqual(onboarding.status_code, 200)

        # Verify no EarnedWages row was created
        async with self.sessions() as session:
            count = (await session.execute(text("SELECT COUNT(*) FROM earned_wages"))).scalar_one()
            self.assertEqual(count, 0, "EarnedWages row should not be created from onboarding income range")

    # Test B: user already has legacy EarnedWages row -> onboarding saved again with different monthly_income_range -> legacy EarnedWages values remain unchanged
    async def test_legacy_earned_wages_preserved_on_onboarding_update(self) -> None:
        token, user_id = await self._register_and_login("demo_safety_b@example.com", name="User B")
        headers = {"Authorization": f"Bearer {token}"}

        # Pre-create a legacy EarnedWages record (simulating existing user data)
        async with self.sessions() as session:
            await session.execute(
                text(
                    "INSERT INTO earned_wages (id, user_id, earned_amount_minor, accessed_amount_minor, available_amount_minor) "
                    "VALUES ('legacy-ew', :uid, 500000, 100000, 400000)"
                ),
                {"uid": user_id},
            )
            await session.commit()

        # Save onboarding with a different monthly_income_range
        onboarding = await self.client.put(
            "/auth/onboarding",
            headers=headers,
            json={"pay_frequency": "monthly", "monthly_income_range": "750,000+"},
        )
        self.assertEqual(onboarding.status_code, 200)

        # Verify the legacy EarnedWages values remain unchanged
        async with self.sessions() as session:
            row = (await session.execute(
                text("SELECT earned_amount_minor, accessed_amount_minor, available_amount_minor FROM earned_wages WHERE user_id = :uid"),
                {"uid": user_id},
            )).first()
            self.assertEqual(row.earned_amount_minor, 500000)
            self.assertEqual(row.accessed_amount_minor, 100000)
            self.assertEqual(row.available_amount_minor, 400000)

    # Test C: monthly_income_range does not create SalaryProfile (already covered by test_salary_safety_onboarding_does_not_create_salary_profile in test_phase12_api.py)
    # This test is a duplicate check for completeness
    async def test_onboarding_does_not_create_salary_profile(self) -> None:
        token, user_id = await self._register_and_login("demo_safety_c@example.com", name="User C")
        headers = {"Authorization": f"Bearer {token}"}

        await self.client.put(
            "/auth/onboarding",
            headers=headers,
            json={"pay_frequency": "monthly", "monthly_income_range": "150,000-300,000"},
        )

        async with self.sessions() as session:
            count = (await session.execute(text("SELECT COUNT(*) FROM salary_profiles"))).scalar_one()
            self.assertEqual(count, 0, "SalaryProfile should not be created from onboarding income range")

    # Test D: existing onboarding fields still persist correctly
    async def test_onboarding_fields_persist_correctly(self) -> None:
        token, user_id = await self._register_and_login("demo_safety_d@example.com", name="User D")
        headers = {"Authorization": f"Bearer {token}"}

        # Save onboarding with all fields
        onboarding_data = {
            "pay_frequency": "monthly",
            "monthly_income_range": "300,000-500,000",
            "payday_range": "15th",
            "financial_pressure": "medium",
            "early_access_use_case": "bills",
            "ai_help_preference": "proactive",
        }
        onboarding = await self.client.put(
            "/auth/onboarding",
            headers=headers,
            json=onboarding_data,
        )
        self.assertEqual(onboarding.status_code, 200)

        # Verify all fields persisted
        response = onboarding.json()
        self.assertEqual(response["pay_frequency"], "monthly")
        self.assertEqual(response["monthly_income_range"], "300,000-500,000")
        self.assertEqual(response["payday_range"], "15th")
        self.assertEqual(response["financial_pressure"], "medium")
        self.assertEqual(response["early_access_use_case"], "bills")
        self.assertEqual(response["ai_help_preference"], "proactive")

        # Verify GET returns the same data
        get_response = await self.client.get("/auth/onboarding", headers=headers)
        self.assertEqual(get_response.status_code, 200)
        get_data = get_response.json()
        self.assertEqual(get_data["pay_frequency"], "monthly")
        self.assertEqual(get_data["monthly_income_range"], "300,000-500,000")
        self.assertEqual(get_data["payday_range"], "15th")
        self.assertEqual(get_data["financial_pressure"], "medium")
        self.assertEqual(get_data["early_access_use_case"], "bills")
        self.assertEqual(get_data["ai_help_preference"], "proactive")


if __name__ == "__main__":
    unittest.main()