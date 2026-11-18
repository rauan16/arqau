from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from alembic import command
from alembic.config import Config

from app.models import Base

ROOT = Path(__file__).resolve().parents[1]
PHASE12_TABLES = ("employers", "employees", "employments", "salary_profiles")
APPLICATION_TABLES = (
    "users",
    "onboarding",
    "transactions",
    "budgets",
    "goals",
    "earned_wages",
    "wage_access_requests",
)

# Columns that must remain unchanged across upgrades. Additive columns
# (e.g. users.role) are intentionally excluded so legacy equality checks
# are not broken by schema growth.
LEGACY_COLUMNS = {
    "users": ("id", "email", "name", "hashed_password", "is_verified", "is_active", "created_at"),
    "onboarding": ("id", "user_id", "pay_frequency", "monthly_income_range", "payday_range", "financial_pressure", "early_access_use_case", "ai_help_preference", "created_at", "updated_at"),
    "transactions": ("id", "user_id", "type", "amount_minor", "category", "merchant", "description", "date", "created_at"),
    "budgets": ("id", "user_id", "category", "limit_minor", "spent_minor", "period", "created_at"),
    "goals": ("id", "user_id", "title", "target_minor", "current_minor", "deadline", "status", "progress_pct", "created_at"),
    "earned_wages": ("id", "user_id", "earned_amount_minor", "accessed_amount_minor", "available_amount_minor", "period_start", "period_end", "created_at", "updated_at"),
    "wage_access_requests": ("id", "user_id", "amount_minor", "status", "reason", "created_at"),
}


PHASE12_INDEXES = (
    "ix_employers_status",
    "ix_employees_user_id",
    "ix_employees_status",
    "ix_employments_employee_id",
    "ix_employments_employer_id",
    "ix_employments_status",
    "ix_salary_profiles_employment_id",
    "ix_salary_profiles_status",
)
PHASE12_CHECK_CONSTRAINTS = ("ck_employments_dates", "ck_salary_profiles_effective_dates")
PHASE12_TABLES = ("employers", "employees", "employments", "salary_profiles")
PHASE13_TABLES = ("refresh_tokens", "employer_admins")
PHASE14_TABLES = ("audit_logs",)
PHASE22_TABLES = ("ewa_policies",)
CURRENT_HEAD = "5c9e8f1a2b3d"


class Phase12MigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.legacy_path = Path(self.temp_dir.name) / "legacy.db"
        shutil.copy2(ROOT / "arqau.db", self.legacy_path)
        self._ensure_clean_legacy_database()

    def _ensure_clean_legacy_database(self) -> None:
        db_path = self.legacy_path
        connection = sqlite3.connect(db_path)
        try:
            for constraint in PHASE12_CHECK_CONSTRAINTS:
                connection.execute(
                    f"DROP INDEX IF EXISTS {constraint}"
                )
            for index in PHASE12_INDEXES:
                connection.execute(f"DROP INDEX IF EXISTS {index}")
            for table in PHASE12_TABLES + PHASE13_TABLES + PHASE14_TABLES + PHASE22_TABLES:
                connection.execute(f"DROP TABLE IF EXISTS {table}")
            connection.execute("DROP TABLE IF EXISTS alembic_version")
            connection.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
            connection.execute(
                "INSERT INTO alembic_version (version_num) VALUES (?)",
                ("20260911_0001",),
            )
            connection.commit()
        finally:
            connection.close()

    def _config(self, database_url: str) -> Config:
        environment = {
            "APP_ENV": "testing",
            "DATABASE_URL": database_url,
            "SECRET_KEY": "test-secret",
            "OPENAI_API_KEY": "test-key",
        }
        patcher = patch.dict(os.environ, environment, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)
        return Config(str(ROOT / "alembic.ini"))

    def _database_url(self, path: Path) -> str:
        return f"sqlite+aiosqlite:///{path.as_posix()}"

    def _snapshot_application_rows(self, path: Path) -> dict[str, list[tuple]]:
        connection = sqlite3.connect(path)
        try:
            existing_tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            rows: dict[str, list[tuple]] = {}
            for table, cols in LEGACY_COLUMNS.items():
                if table not in existing_tables:
                    continue
                col_list = ", ".join(f'"{c}"' for c in cols)
                rows[table] = connection.execute(
                    f"SELECT {col_list} FROM {table} ORDER BY 1"
                ).fetchall()
            return rows
        finally:
            connection.close()

    def test_fresh_sqlite_upgrade_creates_phase12_tables(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "phase12.db"
            config = self._config(self._database_url(database_path))
            command.upgrade(config, "head")
            command.check(config)
            connection = sqlite3.connect(database_path)
            try:
                tables = {
                    row[0]
                    for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
                }
                self.assertTrue(set(PHASE12_TABLES).issubset(tables))
                self.assertTrue(set(PHASE22_TABLES).issubset(tables))
                self.assertEqual(
                    connection.execute("SELECT version_num FROM alembic_version").fetchone(),
                    (CURRENT_HEAD,),
                )
                for table in PHASE12_TABLES:
                    for column in ("id",):
                        count = connection.execute(
                            f"SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?"
                        , (table,)).fetchone()[0]
                        self.assertEqual(count, 1)
            finally:
                connection.close()

    def test_legacy_sqlite_copy_upgrades_without_changing_legacy_data(self) -> None:
        source = self.legacy_path
        self.assertTrue(source.exists())
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "legacy.db"
            shutil.copy2(source, database_path)
            before = self._snapshot_application_rows(database_path)

            config = self._config(self._database_url(database_path))
            command.upgrade(config, "head")

            after = self._snapshot_application_rows(database_path)
            self.assertEqual(before, after)

            connection = sqlite3.connect(database_path)
            try:
                tables = {
                    row[0]
                    for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
                }
                self.assertTrue(set(APPLICATION_TABLES).issubset(tables))
                self.assertTrue(set(PHASE12_TABLES).issubset(tables))
                self.assertTrue(set(PHASE13_TABLES).issubset(tables))
                self.assertTrue(set(PHASE14_TABLES).issubset(tables))
                self.assertTrue(set(PHASE22_TABLES).issubset(tables))
                self.assertEqual(
                    connection.execute("SELECT version_num FROM alembic_version").fetchone(),
                    (CURRENT_HEAD,),
                )
                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            finally:
                connection.close()

    def test_partial_legacy_database_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "partial.db"
            connection = sqlite3.connect(database_path)
            connection.execute("CREATE TABLE users (id VARCHAR PRIMARY KEY, email VARCHAR NOT NULL)")
            connection.commit()
            connection.close()

            config = self._config(self._database_url(database_path))
            with self.assertRaisesRegex(RuntimeError, "partial legacy database"):
                command.upgrade(config, "head")

    def test_downgrade_removes_only_phase12_tables(self) -> None:
        source = self.legacy_path
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "downgrade.db"
            shutil.copy2(source, database_path)
            config = self._config(self._database_url(database_path))
            command.upgrade(config, "head")
            command.downgrade(config, "base")

            connection = sqlite3.connect(database_path)
            try:
                tables = {
                    row[0]
                    for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
                }
                for table in APPLICATION_TABLES:
                    self.assertIn(table, tables)
                for table in PHASE12_TABLES + PHASE13_TABLES + PHASE14_TABLES + PHASE22_TABLES:
                    self.assertNotIn(table, tables)
            finally:
                connection.close()

    def test_upgrade_after_downgrade_works_again(self) -> None:
        source = self.legacy_path
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "reupgrade.db"
            shutil.copy2(source, database_path)
            config = self._config(self._database_url(database_path))
            command.upgrade(config, "head")
            command.downgrade(config, "base")
            before = self._snapshot_application_rows(database_path)
            command.upgrade(config, "head")
            after = self._snapshot_application_rows(database_path)
            self.assertEqual(before, after)
            command.check(config)


if __name__ == "__main__":
    unittest.main()
