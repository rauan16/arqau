from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from sqlalchemy import text

from app.core.database import Base, configure_database, create_database
from app.config import get_settings
from app.database import get_db
from app.main import app

os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("OPENAI_API_KEY", "test-key")


class ApiCompatibilityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "api.db"
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

    async def test_existing_api_contracts_and_crud(self) -> None:
        registration = await self.client.post(
            "/auth/register",
            json={
                "email": "api-contract@example.com",
                "password": "password123",
                "name": "API User",
            },
        )
        self.assertEqual(registration.status_code, 200)
        token_payload = registration.json()
        # TokenResponse is intentionally extended in Phase 1.3 with
        # refresh_token and role; the original three fields remain mandatory.
        self.assertIn("access_token", token_payload)
        self.assertIn("token_type", token_payload)
        self.assertIn("user_id", token_payload)
        self.assertIn("refresh_token", token_payload)
        self.assertIn("role", token_payload)
        token = token_payload["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        me = await self.client.get("/auth/me", headers=headers)
        self.assertEqual(me.status_code, 200)
        self.assertEqual(
            set(me.json()),
            {"id", "email", "name", "is_verified", "is_active", "created_at"},
        )

        onboarding = await self.client.put(
            "/auth/onboarding",
            headers=headers,
            json={"pay_frequency": "monthly", "monthly_income_range": "150,000-300,000"},
        )
        self.assertEqual(onboarding.status_code, 200)
        self.assertEqual(
            set(onboarding.json()),
            {
                "pay_frequency",
                "monthly_income_range",
                "payday_range",
                "financial_pressure",
                "early_access_use_case",
                "ai_help_preference",
            },
        )

        earned = await self.client.put(
            "/ewa/earned", headers=headers, json={"earned_amount_minor": 100000}
        )
        self.assertEqual(earned.status_code, 200)
        self.assertEqual(earned.json()["available_amount_minor"], 100000)

        transaction = await self.client.post(
            "/transactions",
            headers=headers,
            json={
                "type": "income",
                "amount_minor": 6000,
                "category": "Salary",
                "merchant": "Employer",
            },
        )
        self.assertEqual(transaction.status_code, 200)
        self.assertEqual(
            set(transaction.json()),
            {
                "id",
                "user_id",
                "type",
                "amount_minor",
                "category",
                "merchant",
                "description",
                "date",
                "created_at",
            },
        )

        request = await self.client.post(
            "/ewa/request",
            headers=headers,
            json={"amount_minor": 1000, "reason": "Emergency"},
        )
        self.assertEqual(request.status_code, 200)
        self.assertEqual(request.json()["status"], "pending")

        summary = await self.client.get("/finance/summary", headers=headers)
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.json()["total_income_minor"], 6000)
        self.assertEqual(summary.json()["transaction_count"], 1)

        requests = await self.client.get("/ewa/requests", headers=headers)
        self.assertEqual(requests.status_code, 200)
        self.assertEqual(len(requests.json()), 1)

        unauthorized = await self.client.get("/auth/me")
        self.assertEqual(unauthorized.status_code, 401)

    async def test_database_dependency_rolls_back_failed_work(self) -> None:
        async with self.sessions() as session:
            with self.assertRaises(Exception):
                async with session.begin():
                    await session.execute(
                        text(
                            "INSERT INTO users "
                            "(id, email, hashed_password) VALUES "
                            "('rollback-user', 'rollback@example.test', 'hashed')"
                        )
                    )
                    raise RuntimeError("force rollback")

        async with self.sessions() as session:
            result = await session.execute(
                text("SELECT COUNT(*) FROM users WHERE id = 'rollback-user'")
            )
            self.assertEqual(result.scalar_one(), 0)


if __name__ == "__main__":
    unittest.main()
