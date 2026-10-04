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
from app.models import SalaryProfile
from app.main import app

os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("OPENAI_API_KEY", "test-key")


class Phase12ApiTests(unittest.IsolatedAsyncioTestCase):
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

    async def _token(self) -> tuple[str, str]:
        registration = await self.client.post(
            "/auth/register",
            json={"email": "phase12@example.com", "password": "password123", "name": "Phase 12 User"},
        )
        self.assertEqual(registration.status_code, 200)
        user_id = registration.json()["user_id"]
        token = registration.json()["access_token"]
        login = await self.client.post(
            "/auth/login",
            json={"email": "phase12@example.com", "password": "password123"},
        )
        self.assertEqual(login.status_code, 200)
        return token, user_id

    async def test_legacy_auth_onboarding_ewa_finance_and_requests_unchanged(self) -> None:
        token, user_id = await self._token()
        headers = {"Authorization": f"Bearer {token}"}

        onboarding = await self.client.put(
            "/auth/onboarding",
            headers=headers,
            json={"pay_frequency": "monthly", "monthly_income_range": "150,000-300,000"},
        )
        self.assertEqual(onboarding.status_code, 200)

        earned = await self.client.put("/ewa/earned", headers=headers, json={"earned_amount_minor": 100000})
        self.assertEqual(earned.status_code, 200)
        self.assertEqual(earned.json()["available_amount_minor"], 100000)

        transaction = await self.client.post(
            "/transactions",
            headers=headers,
            json={"type": "income", "amount_minor": 6000, "category": "Salary", "merchant": "Employer"},
        )
        self.assertEqual(transaction.status_code, 200)

        # Phase 2 withdrawal requests require a real Employee -> Employment
        # -> SalaryProfile -> EwaPolicy chain; the deterministic engine is the
        # only authoritative source for new withdrawals.
        employer = await self.client.post("/employers/", headers=headers, json={"legal_name": "Acme Corp"})
        self.assertEqual(employer.status_code, 200)
        employer_id = employer.json()["id"]

        employee = await self.client.post("/employees/", headers=headers, json={"user_id": user_id})
        self.assertEqual(employee.status_code, 200)
        employee_id = employee.json()["id"]

        employment = await self.client.post(
            "/employments/",
            headers=headers,
            json={
                "employee_id": employee_id,
                "employer_id": employer_id,
                "start_date": "2026-01-01T00:00:00",
                "status": "active",
            },
        )
        self.assertEqual(employment.status_code, 200)

        salary = await self.client.post(
            "/salary-profiles/",
            headers=headers,
            json={
                "employment_id": employment.json()["id"],
                "currency": "USD",
                "monthly_salary_amount_minor": 100000,
                "pay_schedule": "monthly",
                "effective_from": "2026-01-01T00:00:00",
            },
        )
        self.assertEqual(salary.status_code, 200)

        policy = await self.client.put(
            f"/employers/{employer_id}/ewa/policy",
            headers=headers,
            json={"enabled": True, "max_access_percentage": 50},
        )
        self.assertEqual(policy.status_code, 200)

        request = await self.client.post("/ewa/request", headers=headers, json={"amount_minor": 1000, "reason": "Emergency"})
        self.assertEqual(request.status_code, 200)
        self.assertEqual(request.json()["status"], "pending")

        summary = await self.client.get("/finance/summary", headers=headers)
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.json()["total_income_minor"], 6000)

        requests = await self.client.get("/ewa/requests", headers=headers)
        self.assertEqual(requests.status_code, 200)
        self.assertEqual(len(requests.json()), 1)

        unauthorized = await self.client.get("/auth/me")
        self.assertEqual(unauthorized.status_code, 401)

    async def test_employer_endpoints_work(self) -> None:
        token, _ = await self._token()
        headers = {"Authorization": f"Bearer {token}"}

        created = await self.client.post(
            "/employers/",
            headers=headers,
            json={"legal_name": "Acme Corp", "display_name": "Acme"},
        )
        self.assertEqual(created.status_code, 200)
        employer_id = created.json()["id"]
        self.assertEqual(created.json()["legal_name"], "Acme Corp")

        fetched = await self.client.get(f"/employers/{employer_id}", headers=headers)
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.json()["display_name"], "Acme")

    async def test_employee_duplicate_is_rejected(self) -> None:
        token, user_id = await self._token()
        headers = {"Authorization": f"Bearer {token}"}

        first = await self.client.post(
            "/employees/",
            headers=headers,
            json={"user_id": user_id},
        )
        self.assertEqual(first.status_code, 200)

        second = await self.client.post(
            "/employees/",
            headers=headers,
            json={"user_id": user_id},
        )
        self.assertEqual(second.status_code, 400)

    async def test_employee_nonexistent_user_returns_controlled_error(self) -> None:
        token, _ = await self._token()
        headers = {"Authorization": f"Bearer {token}"}

        response = await self.client.post(
            "/employees/",
            headers=headers,
            json={"user_id": "00000000-0000-0000-0000-000000000000"},
        )
        self.assertNotEqual(response.status_code, 500)
        self.assertEqual(response.status_code, 400)

    async def test_employment_and_salary_lifecycle(self) -> None:
        token, user_id = await self._token()
        headers = {"Authorization": f"Bearer {token}"}

        employer = await self.client.post("/employers/", headers=headers, json={"legal_name": "Acme Corp"})
        employer_id = employer.json()["id"]
        employee = await self.client.post("/employees/", headers=headers, json={"user_id": user_id})
        employee_id = employee.json()["id"]

        invalid_dates = await self.client.post(
            "/employments/",
            headers=headers,
            json={
                "employee_id": employee_id,
                "employer_id": employer_id,
                "start_date": "2026-02-01T00:00:00",
                "end_date": "2026-01-01T00:00:00",
            },
        )
        self.assertEqual(invalid_dates.status_code, 422)

        employment = await self.client.post(
            "/employments/",
            headers=headers,
            json={
                "employee_id": employee_id,
                "employer_id": employer_id,
                "start_date": "2026-01-01T00:00:00",
                "status": "active",
            },
        )
        self.assertEqual(employment.status_code, 200)
        employment_id = employment.json()["id"]

        invalid_salary = await self.client.post(
            "/salary-profiles/",
            headers=headers,
            json={
                "employment_id": employment_id,
                "currency": "USD",
                "monthly_salary_amount_minor": 0,
                "effective_from": "2026-01-01T00:00:00",
            },
        )
        self.assertEqual(invalid_salary.status_code, 422)

        profile = await self.client.post(
            "/salary-profiles/",
            headers=headers,
            json={
                "employment_id": employment_id,
                "currency": "USD",
                "monthly_salary_amount_minor": 100000,
                "pay_schedule": "monthly",
                "payday_day": 1,
                "effective_from": "2026-01-01T00:00:00",
            },
        )
        self.assertEqual(profile.status_code, 200)
        profile_id = profile.json()["id"]

        fetched = await self.client.get(f"/salary-profiles/{profile_id}", headers=headers)
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.json()["monthly_salary_amount_minor"], 100000)

        updated = await self.client.put(
            f"/salary-profiles/{profile_id}",
            headers=headers,
            json={"monthly_salary_amount_minor": 120000},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["monthly_salary_amount_minor"], 120000)

    async def test_salary_safety_onboarding_does_not_create_salary_profile(self) -> None:
        token, user_id = await self._token()
        headers = {"Authorization": f"Bearer {token}"}

        await self.client.put(
            "/auth/onboarding",
            headers=headers,
            json={"pay_frequency": "monthly", "monthly_income_range": "150,000-300,000"},
        )
        await self.client.post(
            "/employees/",
            headers=headers,
            json={"user_id": user_id},
        )

        async with self.sessions() as session:
            count = await session.execute(
                text("SELECT COUNT(*) FROM salary_profiles")
            )
            self.assertEqual(count.scalar_one(), 0)


if __name__ == "__main__":
    unittest.main()
