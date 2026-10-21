from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import httpx

from app.core.database import Base, configure_database, create_database
from app.config import get_settings
from app.database import get_db
from app.main import app
from app.core.auth_rate_limit import _reset_all_limiters

os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("OPENAI_API_KEY", "test-key")


class Phase13RbacTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        _reset_all_limiters()
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "rbac.db"
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

    # -- helpers -------------------------------------------------------

    async def _register(self, email: str, password: str = "password123", name: str | None = None):
        body = {"email": email, "password": password}
        if name is not None:
            body["name"] = name
        response = await self.client.post("/auth/register", json=body)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    async def _login(self, email: str, password: str = "password123"):
        response = await self.client.post("/auth/login", json={"email": email, "password": password})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

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
        self, token: str, employment_id: str, amount: int = 100000
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

    async def _promote(self, super_token: str, user_id: str, role: str) -> None:
        response = await self.client.post(
            f"/admin/users/{user_id}/role",
            headers={"Authorization": f"Bearer {super_token}"},
            json={"role": role},
        )
        self.assertEqual(response.status_code, 200, response.text)

    async def _set_role_direct(self, user_id: str, role: str) -> None:
        """Bypass the /admin endpoint for bootstrapping the first super admin."""
        from sqlalchemy import text

        async with self.sessions() as session:
            await session.execute(
                text("UPDATE users SET role = :role WHERE id = :uid"),
                {"role": role, "uid": user_id},
            )
            await session.commit()

    async def _add_admin(self, super_token: str, user_id: str, employer_id: str) -> None:
        response = await self.client.post(
            "/admin/employer-admins",
            headers={"Authorization": f"Bearer {super_token}"},
            json={"user_id": user_id, "employer_id": employer_id},
        )
        self.assertEqual(response.status_code, 201, response.text)

    # -- setup ---------------------------------------------------------

    async def _build_two_tenants(self) -> dict:
        super_user = await self._register("super@example.com", name="Super")
        # Bootstrap the first super_admin directly: the /admin endpoint
        # requires an existing super_admin, so the initial grant must not
        # depend on itself.
        await self._set_role_direct(super_user["user_id"], "super_admin")
        # Refresh the access token so the new role is reflected in the JWT.
        super_user = await self._login("super@example.com")

        a_user = await self._register("a@example.com", name="A")
        b_user = await self._register("b@example.com", name="B")
        # A plain employee (no admin membership) used for employee-scope tests.
        c_user = await self._register("c@example.com", name="C")

        a_employer = await self._create_employer(super_user["access_token"], "Acme A")
        b_employer = await self._create_employer(super_user["access_token"], "Acme B")

        a_employee = await self._create_employee(super_user["access_token"], a_user["user_id"])
        b_employee = await self._create_employee(super_user["access_token"], b_user["user_id"])
        c_employee = await self._create_employee(super_user["access_token"], c_user["user_id"])

        a_employment = await self._create_employment(
            super_user["access_token"], a_employee, a_employer
        )
        b_employment = await self._create_employment(
            super_user["access_token"], b_employee, b_employer
        )
        c_employment = await self._create_employment(
            super_user["access_token"], c_employee, a_employer
        )

        a_salary = await self._create_salary(super_user["access_token"], a_employment)
        b_salary = await self._create_salary(super_user["access_token"], b_employment)
        c_salary = await self._create_salary(super_user["access_token"], c_employment)

        # Make A an employer_admin for Employer A.
        await self._add_admin(super_user["access_token"], a_user["user_id"], a_employer)
        await self._promote(super_user["access_token"], a_user["user_id"], "employer_admin")

        return {
            "super": super_user,
            "a": a_user,
            "b": b_user,
            "c": c_user,
            "a_employer": a_employer,
            "b_employer": b_employer,
            "a_employee": a_employee,
            "b_employee": b_employee,
            "c_employee": c_employee,
            "a_employment": a_employment,
            "b_employment": b_employment,
            "c_employment": c_employment,
            "a_salary": a_salary,
            "b_salary": b_salary,
            "c_salary": c_salary,
        }

    # -- RBAC assertions ----------------------------------------------

    async def test_employee_can_only_access_own_data(self) -> None:
        ctx = await self._build_two_tenants()
        c_headers = {"Authorization": f"Bearer {ctx['c']['access_token']}"}

        # Employee C reads own employee.
        own = await self.client.get(f"/employees/{ctx['c_employee']}", headers=c_headers)
        self.assertEqual(own.status_code, 200)

        # Employee C cannot read Employee B.
        other = await self.client.get(f"/employees/{ctx['b_employee']}", headers=c_headers)
        self.assertEqual(other.status_code, 404)

        # Employee C cannot read B's employment.
        emp = await self.client.get(f"/employments/{ctx['b_employment']}", headers=c_headers)
        self.assertEqual(emp.status_code, 404)

        # Employee C cannot read B's salary profile.
        sal = await self.client.get(f"/salary-profiles/{ctx['b_salary']}", headers=c_headers)
        self.assertEqual(sal.status_code, 404)

        # Employee C cannot create an employment (mutation).
        create = await self.client.post(
            "/employments/",
            headers=c_headers,
            json={
                "employee_id": ctx["c_employee"],
                "employer_id": ctx["a_employer"],
                "start_date": "2026-01-01T00:00:00",
            },
        )
        self.assertEqual(create.status_code, 403)

    async def test_employer_admin_scoped_to_own_employer(self) -> None:
        ctx = await self._build_two_tenants()
        a_headers = {"Authorization": f"Bearer {ctx['a']['access_token']}"}

        # Own resources accessible.
        self.assertEqual(
            (await self.client.get(f"/employers/{ctx['a_employer']}", headers=a_headers)).status_code, 200
        )
        self.assertEqual(
            (await self.client.get(f"/employees/{ctx['a_employee']}", headers=a_headers)).status_code, 200
        )
        self.assertEqual(
            (await self.client.get(f"/employments/{ctx['a_employment']}", headers=a_headers)).status_code, 200
        )
        self.assertEqual(
            (await self.client.get(f"/salary-profiles/{ctx['a_salary']}", headers=a_headers)).status_code, 200
        )

        # Cross-tenant resources denied.
        self.assertEqual(
            (await self.client.get(f"/employers/{ctx['b_employer']}", headers=a_headers)).status_code, 404
        )
        self.assertEqual(
            (await self.client.get(f"/employees/{ctx['b_employee']}", headers=a_headers)).status_code, 404
        )
        self.assertEqual(
            (await self.client.get(f"/employments/{ctx['b_employment']}", headers=a_headers)).status_code, 404
        )
        self.assertEqual(
            (await self.client.get(f"/salary-profiles/{ctx['b_salary']}", headers=a_headers)).status_code, 404
        )

        # Admin A cannot mutate B's salary profile.
        put = await self.client.put(
            f"/salary-profiles/{ctx['b_salary']}",
            headers=a_headers,
            json={"monthly_salary_amount_minor": 999},
        )
        self.assertEqual(put.status_code, 404)

    async def test_forged_employer_id_in_body_is_rejected(self) -> None:
        ctx = await self._build_two_tenants()
        a_headers = {"Authorization": f"Bearer {ctx['a']['access_token']}"}

        # Admin A tries to create an employment under Employer B.
        response = await self.client.post(
            "/employments/",
            headers=a_headers,
            json={
                "employee_id": ctx["a_employee"],
                "employer_id": ctx["b_employer"],
                "start_date": "2026-01-01T00:00:00",
            },
        )
        self.assertEqual(response.status_code, 404)

        # Admin A tries to create a salary profile for an employment under B.
        response = await self.client.post(
            "/salary-profiles/",
            headers=a_headers,
            json={
                "employment_id": ctx["b_employment"],
                "currency": "USD",
                "monthly_salary_amount_minor": 100000,
                "effective_from": "2026-01-01T00:00:00",
            },
        )
        self.assertEqual(response.status_code, 404)

    async def test_super_admin_has_broad_access(self) -> None:
        ctx = await self._build_two_tenants()
        super_headers = {"Authorization": f"Bearer {ctx['super']['access_token']}"}

        self.assertEqual(
            (await self.client.get(f"/employers/{ctx['b_employer']}", headers=super_headers)).status_code, 200
        )
        self.assertEqual(
            (await self.client.get(f"/employees/{ctx['b_employee']}", headers=super_headers)).status_code, 200
        )
        self.assertEqual(
            (await self.client.get(f"/employments/{ctx['b_employment']}", headers=super_headers)).status_code, 200
        )
        self.assertEqual(
            (await self.client.get(f"/salary-profiles/{ctx['b_salary']}", headers=super_headers)).status_code, 200
        )


if __name__ == "__main__":
    unittest.main()
