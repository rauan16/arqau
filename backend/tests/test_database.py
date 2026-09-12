from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import inspect, text

from app.core.database import Base, configure_database, create_database
from app.config import get_settings
from app.main import app
from app.models import Budget, Goal, Onboarding, Transaction, User


class DatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "test.db"
        self.database_url = f"sqlite+aiosqlite:///{self.database_path.as_posix()}"
        self.original_url = get_settings().database_url
        self.engine, self.sessions = create_database(self.database_url)
        await configure_database(self.database_url)

    async def asyncTearDown(self) -> None:
        if self.original_url:
            await configure_database(self.original_url)
        await self.engine.dispose()
        self.temp_dir.cleanup()

    async def test_sqlite_startup_and_session_creation(self) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with self.sessions() as session:
            pragma = await session.execute(text("PRAGMA foreign_keys"))
            self.assertEqual(pragma.scalar_one(), 1)

        with TestClient(app) as client:
            response = client.get("/health")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"status": "ok"})

    async def test_model_crud_and_relationships(self) -> None:
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
            await session.refresh(user)

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
            session.add_all([onboarding, transaction, budget, goal])
            await session.commit()

            result = await session.execute(
                text("SELECT COUNT(*) FROM users WHERE id = :user_id"),
                {"user_id": user.id},
            )
            self.assertEqual(result.scalar_one(), 1)
            self.assertEqual(onboarding.user.id, user.id)
            self.assertEqual(transaction.user_id, user.id)
            self.assertEqual(budget.user_id, user.id)
            self.assertEqual(goal.user_id, user.id)

    async def test_production_lifespan_does_not_create_schema(self) -> None:
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)

        from app import config
        from app import main

        production_settings = config.Settings(
            environment="production",
            database_url="postgresql+asyncpg://user:password@localhost/arqau",
            secret_key="production-secret",
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
