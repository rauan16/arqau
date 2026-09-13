from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import httpx
from sqlalchemy import select, text

from app.api.v1.auth import get_current_user
from app.config import get_settings
from app.core.database import Base, configure_database, create_database
from app.database import get_db
from app.main import app
from app.models import AuditLog
from app.services.audit_service import (
    EMPLOYEE_CREATED,
    EMPLOYER_ADMIN_ASSIGNED,
    EMPLOYER_CREATED,
    EMPLOYMENT_CREATED,
    SALARY_PROFILE_CREATED,
    SALARY_PROFILE_UPDATED,
    USER_REQUESTED_WITHDRAWAL,
    USER_ROLE_CHANGED,
    record_audit_event,
)

os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("OPENAI_API_KEY", "test-key")


class Phase14AuditTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "audit.db"
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

    async def _register(
        self, email: str, password: str = "AuditPassword123!", name: str | None = None
    ) -> dict:
        body = {"email": email, "password": password}
        if name is not None:
            body["name"] = name
        response = await self.client.post("/auth/register", json=body)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    async def _login(self, email: str, password: str = "AuditPassword123!") -> dict:
        response = await self.client.post(
            "/auth/login", json={"email": email, "password": password}
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    async def _set_role_direct(self, user_id: str, role: str) -> None:
        async with self.sessions() as session:
            await session.execute(
                text("UPDATE users SET role = :role WHERE id = :user_id"),
                {"role": role, "user_id": user_id},
            )
            await session.commit()

    async def _create_employer(self, token: str, legal_name: str) -> str:
        response = await self.client.post(
            "/employers/",
            headers={"Authorization": f"Bearer {token}"},
            json={"legal_name": legal_name},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["id"]

    async def _create_employee(self, token: str, user_id: str) -> str:
        response = await self.client.post(
            "/employees/",
            headers={"Authorization": f"Bearer {token}"},
            json={"user_id": user_id},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["id"]

    async def _create_employment(
        self, token: str, employee_id: str, employer_id: str
    ) -> str:
        response = await self.client.post(
            "/employments/",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "employee_id": employee_id,
                "employer_id": employer_id,
                "start_date": "2026-01-01T00:00:00",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["id"]

    async def _create_salary(
        self, token: str, employment_id: str, amount: int = 100_000
    ) -> str:
        response = await self.client.post(
            "/salary-profiles/",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "employment_id": employment_id,
                "currency": "USD",
                "monthly_salary_amount_minor": amount,
                "effective_from": "2026-01-01T00:00:00",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["id"]

    async def _update_salary(
        self, token: str, salary_id: str, amount: int
    ) -> dict:
        response = await self.client.put(
            f"/salary-profiles/{salary_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"monthly_salary_amount_minor": amount},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    async def _assign_admin(self, token: str, user_id: str, employer_id: str) -> None:
        response = await self.client.post(
            "/admin/employer-admins",
            headers={"Authorization": f"Bearer {token}"},
            json={"user_id": user_id, "employer_id": employer_id},
        )
        self.assertEqual(response.status_code, 201, response.text)

    async def _promote(self, token: str, user_id: str, role: str) -> None:
        response = await self.client.post(
            f"/admin/users/{user_id}/role",
            headers={"Authorization": f"Bearer {token}"},
            json={"role": role},
        )
        self.assertEqual(response.status_code, 200, response.text)

    async def _set_earned(self, token: str, amount: int) -> None:
        response = await self.client.put(
            "/ewa/earned",
            headers={"Authorization": f"Bearer {token}"},
            json={"earned_amount_minor": amount},
        )
        self.assertEqual(response.status_code, 200, response.text)

    async def _request_withdrawal(self, token: str, amount: int) -> dict:
        response = await self.client.post(
            "/ewa/request",
            headers={"Authorization": f"Bearer {token}"},
            json={"amount_minor": amount, "reason": "Audit test"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    async def _audit_rows(self) -> list[AuditLog]:
        async with self.sessions() as session:
            result = await session.execute(
                select(AuditLog).order_by(AuditLog.created_at, AuditLog.id)
            )
            return list(result.scalars().all())

    async def _bootstrap_super_admin(self) -> tuple[dict, str]:
        user = await self._register("super@audit.example.com", name="Super")
        await self._set_role_direct(user["user_id"], "super_admin")
        user = await self._login("super@audit.example.com")
        return user, user["access_token"]

    @staticmethod
    def _assert_no_sensitive_values(
        value: object, forbidden_values: set[str], path: str = "$"
    ) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                normalized_key = "".join(
                    character for character in key.lower() if character.isalnum()
                )
                unittest.TestCase().assertFalse(
                    any(
                        marker in normalized_key
                        for marker in ("password", "token", "secret", "apikey", "authorization", "cookie")
                    ),
                    f"sensitive metadata key at {path}.{key}",
                )
                Phase14AuditTests._assert_no_sensitive_values(
                    child, forbidden_values, f"{path}.{key}"
                )
            return
        if isinstance(value, list):
            for index, child in enumerate(value):
                Phase14AuditTests._assert_no_sensitive_values(
                    child, forbidden_values, f"{path}[{index}]"
                )
            return
        if isinstance(value, str):
            unittest.TestCase().assertNotIn(value, forbidden_values, path)

    def _assert_audit_payloads_are_safe(
        self, rows: list[AuditLog], forbidden_values: set[str]
    ) -> None:
        for row in rows:
            for field in ("details", "before_data", "after_data"):
                payload = getattr(row, field)
                if payload is not None:
                    self._assert_no_sensitive_values(payload, forbidden_values, f"{row.action}.{field}")

    async def _build_rbac_context(self) -> dict:
        super_user, super_token = await self._bootstrap_super_admin()
        admin_user = await self._register("admin@audit.example.com", name="Admin")
        finance_user = await self._register("finance@audit.example.com", name="Finance")
        employee_user = await self._register("employee@audit.example.com", name="Employee")

        employer_a = await self._create_employer(super_token, "Audit Employer A")
        employer_b = await self._create_employer(super_token, "Audit Employer B")
        admin_employee = await self._create_employee(super_token, admin_user["user_id"])
        finance_employee = await self._create_employee(super_token, finance_user["user_id"])
        employee_employee = await self._create_employee(super_token, employee_user["user_id"])
        admin_employment = await self._create_employment(
            super_token, admin_employee, employer_a
        )
        finance_employment = await self._create_employment(
            super_token, finance_employee, employer_a
        )
        employee_employment = await self._create_employment(
            super_token, employee_employee, employer_b
        )
        await self._create_salary(super_token, admin_employment)
        await self._create_salary(super_token, finance_employment)
        await self._create_salary(super_token, employee_employment)

        await self._assign_admin(super_token, admin_user["user_id"], employer_a)
        await self._promote(super_token, admin_user["user_id"], "employer_admin")
        admin_token = (await self._login("admin@audit.example.com"))["access_token"]

        await self._assign_admin(super_token, finance_user["user_id"], employer_a)
        await self._promote(super_token, finance_user["user_id"], "finance_manager")
        finance_token = (await self._login("finance@audit.example.com"))["access_token"]

        employee_token = (await self._login("employee@audit.example.com"))["access_token"]
        return {
            "super_token": super_token,
            "admin_token": admin_token,
            "finance_token": finance_token,
            "employee_token": employee_token,
            "employer_a": employer_a,
            "employer_b": employer_b,
        }

    async def test_required_audit_events_and_safe_metadata(self) -> None:
        super_user, super_token = await self._bootstrap_super_admin()
        employee_user = await self._register("worker@audit.example.com", name="Worker")

        employer_id = await self._create_employer(super_token, "Audit Lifecycle Ltd")
        employee_id = await self._create_employee(
            super_token, employee_user["user_id"]
        )
        employment_id = await self._create_employment(
            super_token, employee_id, employer_id
        )
        salary_id = await self._create_salary(super_token, employment_id)
        await self._update_salary(super_token, salary_id, 125_000)

        finance_user = await self._register("finance-worker@audit.example.com", name="Finance Worker")
        await self._assign_admin(super_token, finance_user["user_id"], employer_id)
        await self._promote(super_token, finance_user["user_id"], "finance_manager")

        employee_token = (await self._login("worker@audit.example.com"))["access_token"]
        await self._set_earned(employee_token, 10_000)
        await self._request_withdrawal(employee_token, 1_000)

        rows = await self._audit_rows()
        by_action = {action: [row for row in rows if row.action == action] for action in {row.action for row in rows}}
        required_actions = {
            EMPLOYER_CREATED,
            EMPLOYEE_CREATED,
            EMPLOYMENT_CREATED,
            SALARY_PROFILE_CREATED,
            SALARY_PROFILE_UPDATED,
            USER_ROLE_CHANGED,
            EMPLOYER_ADMIN_ASSIGNED,
            USER_REQUESTED_WITHDRAWAL,
        }
        self.assertTrue(required_actions.issubset(by_action), required_actions - set(by_action))
        for action in required_actions:
            self.assertEqual(len(by_action[action]), 1, action)

        employer_event = by_action[EMPLOYER_CREATED][0]
        self.assertEqual(employer_event.actor_user_id, super_user["user_id"])
        self.assertEqual(employer_event.employer_id, employer_id)
        self.assertEqual(employer_event.entity_id, employer_id)

        employee_event = by_action[EMPLOYEE_CREATED][0]
        self.assertEqual(employee_event.actor_user_id, super_user["user_id"])
        self.assertEqual(employee_event.entity_id, employee_id)
        self.assertEqual(employee_event.details["user_id"], employee_user["user_id"])

        employment_event = by_action[EMPLOYMENT_CREATED][0]
        self.assertEqual(employment_event.employer_id, employer_id)
        self.assertEqual(employment_event.entity_id, employment_id)

        salary_create_event = by_action[SALARY_PROFILE_CREATED][0]
        salary_update_event = by_action[SALARY_PROFILE_UPDATED][0]
        self.assertEqual(salary_create_event.employer_id, employer_id)
        self.assertEqual(salary_update_event.employer_id, employer_id)
        self.assertEqual(salary_create_event.entity_id, salary_id)
        self.assertEqual(salary_update_event.entity_id, salary_id)
        self.assertEqual(salary_update_event.details["before"]["monthly_salary_amount_minor"], 100_000)
        self.assertEqual(salary_update_event.details["after"]["monthly_salary_amount_minor"], 125_000)

        role_event = by_action[USER_ROLE_CHANGED][0]
        self.assertEqual(role_event.actor_user_id, super_user["user_id"])
        self.assertEqual(role_event.entity_id, finance_user["user_id"])
        self.assertEqual(role_event.details["previous_role"], "employee")
        self.assertEqual(role_event.details["new_role"], "finance_manager")

        admin_event = by_action[EMPLOYER_ADMIN_ASSIGNED][0]
        self.assertEqual(admin_event.employer_id, employer_id)
        self.assertEqual(admin_event.entity_type, "employer_admin")
        self.assertEqual(admin_event.details["user_id"], finance_user["user_id"])

        withdrawal_event = by_action[USER_REQUESTED_WITHDRAWAL][0]
        self.assertEqual(withdrawal_event.actor_user_id, employee_user["user_id"])
        self.assertIsNone(withdrawal_event.employer_id)
        self.assertEqual(withdrawal_event.details["amount_minor"], 1_000)

        forbidden_values = {
            "AuditPassword123!",
            super_user["access_token"],
            super_user["refresh_token"],
            employee_token,
        }
        self._assert_audit_payloads_are_safe(rows, forbidden_values)

    async def test_audit_metadata_sanitizes_sensitive_fields(self) -> None:
        metadata = {
            "safe": {"employer_id": "employer-safe"},
            "password": "metadata-password",
            "access_token": "metadata-access-token",
            "refresh_token": "metadata-refresh-token",
            "secret": "metadata-secret",
            "api_key": "metadata-api-key",
            "authorization": "metadata-authorization",
            "nested": {
                "cookie": "metadata-cookie",
                "safe_value": "kept",
            },
        }
        async with self.sessions() as session:
            row = await record_audit_event(
                session,
                action="SANITIZER_TEST",
                metadata=metadata,
                before_data={"password": "before-password", "safe": True},
                after_data={"refresh_token": "after-refresh-token", "safe": True},
            )
            await session.commit()

        self.assertEqual(row.details, {"safe": {"employer_id": "employer-safe"}, "nested": {"safe_value": "kept"}})
        self.assertEqual(row.before_data, {"safe": True})
        self.assertEqual(row.after_data, {"safe": True})
        self._assert_no_sensitive_values(
            row.details,
            {"metadata-password", "metadata-access-token", "metadata-refresh-token", "metadata-secret", "metadata-api-key", "metadata-authorization", "metadata-cookie"},
        )

    async def test_audit_log_read_is_employer_scoped(self) -> None:
        context = await self._build_rbac_context()
        employer_a = context["employer_a"]
        employer_b = context["employer_b"]

        super_headers = {"Authorization": f"Bearer {context['super_token']}"}
        admin_headers = {"Authorization": f"Bearer {context['admin_token']}"}
        finance_headers = {"Authorization": f"Bearer {context['finance_token']}"}
        employee_headers = {"Authorization": f"Bearer {context['employee_token']}"}

        employee_response = await self.client.get("/admin/audit-logs", headers=employee_headers)
        self.assertEqual(employee_response.status_code, 403, employee_response.text)

        admin_response = await self.client.get("/admin/audit-logs", headers=admin_headers)
        self.assertEqual(admin_response.status_code, 200, admin_response.text)
        admin_rows = admin_response.json()
        self.assertTrue(admin_rows)
        self.assertTrue(all(row["employer_id"] == employer_a for row in admin_rows))
        self.assertNotIn(employer_b, {row["employer_id"] for row in admin_rows})

        bypass_response = await self.client.get(
            "/admin/audit-logs",
            headers=admin_headers,
            params={"employer_id": employer_b},
        )
        self.assertEqual(bypass_response.status_code, 200, bypass_response.text)
        self.assertTrue(
            all(row["employer_id"] == employer_a for row in bypass_response.json())
        )

        finance_response = await self.client.get("/admin/audit-logs", headers=finance_headers)
        self.assertEqual(finance_response.status_code, 200, finance_response.text)
        self.assertTrue(
            all(row["employer_id"] == employer_a for row in finance_response.json())
        )

        super_response = await self.client.get(
            "/admin/audit-logs",
            headers=super_headers,
            params={"employer_id": employer_b},
        )
        self.assertEqual(super_response.status_code, 200, super_response.text)
        super_rows = super_response.json()
        self.assertTrue(super_rows)
        self.assertTrue(all(row["employer_id"] == employer_b for row in super_rows))

    async def test_salary_profile_audit_employer_id_matches_employment(self) -> None:
        _, super_token = await self._bootstrap_super_admin()
        user = await self._register("salary-owner@audit.example.com", name="Salary Owner")
        employer_id = await self._create_employer(super_token, "Salary Employer")
        employee_id = await self._create_employee(super_token, user["user_id"])
        employment_id = await self._create_employment(
            super_token, employee_id, employer_id
        )
        salary_id = await self._create_salary(super_token, employment_id)
        await self._update_salary(super_token, salary_id, 150_000)

        rows = await self._audit_rows()
        salary_events = [
            row
            for row in rows
            if row.entity_id == salary_id
            and row.action in {SALARY_PROFILE_CREATED, SALARY_PROFILE_UPDATED}
        ]
        self.assertEqual(
            {row.action for row in salary_events},
            {SALARY_PROFILE_CREATED, SALARY_PROFILE_UPDATED},
        )
        for row in salary_events:
            self.assertEqual(row.employer_id, employer_id)

        async with self.sessions() as session:
            employment_employer_id = await session.scalar(
                text("SELECT employer_id FROM employments WHERE id = :employment_id"),
                {"employment_id": employment_id},
            )
        self.assertEqual(employment_employer_id, employer_id)


if __name__ == "__main__":
    unittest.main()
