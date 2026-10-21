from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import selectinload

from app.core.database import Base, configure_database, create_database
from app.config import get_settings
from app.main import app
from app.models import (
    Budget,
    Employee,
    Employer,
    Employment,
    Goal,
    Onboarding,
    SalaryProfile,
    Transaction,
    User,
)


class Phase12DatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "db.db"
        self.database_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
        self.original_url = get_settings().database_url
        self.engine, self.sessions = create_database(self.database_url)
        await configure_database(self.database_url)

    async def asyncTearDown(self) -> None:
        if self.original_url:
            await configure_database(self.original_url)
        await self.engine.dispose()
        self.temp_dir.cleanup()

    async def test_sqlite_startup_and_foreign_keys(self) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with self.sessions() as session:
            pragma = await session.execute(text("PRAGMA foreign_keys"))
            self.assertEqual(pragma.scalar_one(), 1)

        with TestClient(app) as client:
            response = client.get("/health")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"status": "ok"})

    async def test_phase12_model_metadata_compiles_for_postgresql(self) -> None:
        from sqlalchemy.dialects import postgresql
        from sqlalchemy.schema import CreateTable

        dialect = postgresql.dialect()
        for table in Base.metadata.sorted_tables:
            compiled = str(CreateTable(table).compile(dialect=dialect))
            self.assertIn(f"CREATE TABLE {table.name}", compiled)
            for column in table.columns:
                if column.primary_key:
                    self.assertIn(column.name, compiled)

    async def test_phase12_model_crud_and_relationships(self) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with self.sessions() as session:
            user = User(
                id="user-1",
                email="crud@example.test",
                name="CRUD User",
                hashed_password="hashed",
            )
            session.add(user)
            await session.commit()

            onboarding = Onboarding(
                id="onboarding-1",
                user_id=user.id,
                pay_frequency="monthly",
                monthly_income_range="150,000-300,000",
            )
            transaction = Transaction(
                id="transaction-1",
                user_id=user.id,
                type="income",
                amount_minor=1000,
                category="Salary",
            )
            budget = Budget(
                id="budget-1",
                user_id=user.id,
                category="Food",
                limit_minor=500,
                spent_minor=100,
            )
            goal = Goal(
                id="goal-1",
                user_id=user.id,
                title="Reserve",
                target_minor=1000,
                current_minor=250,
            )
            employer = Employer(legal_name="Acme Corp")
            employee = Employee(user_id=user.id, external_employee_id="EMP-1")
            session.add_all([onboarding, transaction, budget, goal, employer, employee])
            await session.flush()

            employment = Employment(employee_id=employee.id, employer_id=employer.id)
            session.add(employment)
            await session.flush()

            profile = SalaryProfile(
                employment_id=employment.id,
                currency="USD",
                monthly_salary_amount_minor=1000,
                effective_from=datetime(2026, 1, 1),
            )
            session.add_all([employment, profile])
            await session.commit()

            result = await session.execute(
                text("SELECT COUNT(*) FROM users WHERE id = :user_id"),
                {"user_id": user.id},
            )
            self.assertEqual(result.scalar_one(), 1)

            emp_result = await session.execute(
                select(Employee)
                .where(Employee.id == employee.id)
                .options(selectinload(Employee.user))
            )
            loaded_employee = emp_result.scalar_one()
            self.assertEqual(loaded_employee.user.id, user.id)

            empl_result = await session.execute(
                select(Employment)
                .where(Employment.id == employment.id)
                .options(
                    selectinload(Employment.employee),
                    selectinload(Employment.employer),
                    selectinload(Employment.salary_profile),
                )
            )
            loaded_employment = empl_result.scalar_one()
            self.assertEqual(loaded_employment.employee.id, employee.id)
            self.assertEqual(loaded_employment.employer.id, employer.id)
            self.assertEqual(loaded_employment.salary_profile.id, profile.id)

            prof_result = await session.execute(
                select(SalaryProfile)
                .where(SalaryProfile.id == profile.id)
                .options(selectinload(SalaryProfile.employment))
            )
            loaded_profile = prof_result.scalar_one()
            self.assertEqual(loaded_profile.employment.id, employment.id)

    async def test_production_lifespan_does_not_create_schema(self) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)

        from app import config
        from app import main

        production_settings = config.Settings(
            environment="production",
            database_url="postgresql+asyncpg://user:password@localhost/arqau",
            secret_key="p" * 32,
            cors_origins="https://example.test",
            openai_api_key="server-key",
        )
        with patch.object(main, "settings", production_settings):
            async with app.router.lifespan_context(app):
                pass

        async with self.engine.connect() as connection:
            table_names = await connection.run_sync(
                lambda sync_connection: inspect(sync_connection).get_table_names()
            )
        self.assertNotIn("users", table_names)


if __name__ == "__main__":
    unittest.main()

