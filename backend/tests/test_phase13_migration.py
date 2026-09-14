"""Phase 1.3 migration validation on disposable SQLite databases.

Covers:
- fresh DB upgrade to head
- Phase 1.2 -> Phase 1.3 upgrade (legacy copy)
- downgrade head -> base and re-upgrade
- legacy data preservation (column-aware snapshot)
- PostgreSQL DDL compilation for all tables
"""
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

APPLICATION_TABLES = (
    "users",
    "onboarding",
    "transactions",
    "budgets",
    "goals",
    "earned_wages",
    "wage_access_requests",
)
PHASE12_TABLES = ("employers", "employees", "employments", "salary_profiles")
PHASE13_TABLES = ("refresh_tokens", "employer_admins")
PHASE14_TABLES = ("audit_logs",)
PHASE22_TABLES = ("ewa_policies",)
CURRENT_HEAD = "4b8dc4775b9b"

# Columns that must remain unchanged across Phase 1.3 upgrades. Additive
# columns (e.g. users.role) are intentionally excluded so legacy equality
# checks are not broken by schema growth.
LEGACY_COLUMNS = {
    "users": ("id", "email", "name", "hashed_password", "is_verified", "is_active", "created_at"),
    "onboarding": ("id", "user_id", "pay_frequency", "monthly_income_range", "payday_range", "financial_pressure", "early_access_use_case", "ai_help_preference", "created_at", "updated_at"),
    "transactions": ("id", "user_id", "type", "amount_minor", "category", "merchant", "description", "date", "created_at"),
    "budgets": ("id", "user_id", "category", "limit_minor", "spent_minor", "period", "created_at"),
    "goals": ("id", "user_id", "title", "target_minor", "current_minor", "deadline", "status", "progress_pct", "created_at"),
    "earned_wages": ("id", "user_id", "earned_amount_minor", "accessed_amount_minor", "available_amount_minor", "period_start", "period_end", "created_at", "updated_at"),
    "wage_access_requests": ("id", "user_id", "amount_minor", "status", "reason", "created_at"),
}


def _config(database_url: str) -> Config:
    environment = {
        "APP_ENV": "testing",
        "DATABASE_URL": database_url,
        "SECRET_KEY": "test-secret",
        "OPENAI_API_KEY": "test-key",
    }
    patcher = patch.dict(os.environ, environment, clear=False)
    patcher.start()
    return Config(str(ROOT / "alembic.ini"))


def _database_url(path: Path) -> str:
    return f"sqlite+aiosqlite:///{path.as_posix()}"


def _snapshot(path: Path) -> dict[str, list[tuple]]:
    connection = sqlite3.connect(path)
    try:
        existing_tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
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


def _tables(path: Path) -> set[str]:
    connection = sqlite3.connect(path)
    try:
        return {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    finally:
        connection.close()


class Phase13MigrationTests(unittest.TestCase):
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
            for constraint in ("ck_employments_dates", "ck_salary_profiles_effective_dates"):
                connection.execute(f"DROP INDEX IF EXISTS {constraint}")
            for index in (
                "ix_employers_status",
                "ix_employees_user_id",
                "ix_employees_status",
                "ix_employments_employee_id",
                "ix_employments_employer_id",
                "ix_employments_status",
                "ix_salary_profiles_employment_id",
                "ix_salary_profiles_status",
            ):
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

    def test_fresh_database_upgrades_to_head(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "fresh.db"
            config = _config(_database_url(database_path))
            command.upgrade(config, "head")
            command.check(config)
            tables = _tables(database_path)
            self.assertTrue(set(APPLICATION_TABLES).issubset(tables))
            self.assertTrue(set(PHASE12_TABLES).issubset(tables))
            self.assertTrue(set(PHASE13_TABLES).issubset(tables))
            self.assertTrue(set(PHASE14_TABLES).issubset(tables))
            self.assertTrue(set(PHASE22_TABLES).issubset(tables))

            connection = sqlite3.connect(database_path)
            try:
                self.assertEqual(
                    connection.execute("SELECT version_num FROM alembic_version").fetchone(),
                    (CURRENT_HEAD,),
                )
                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            finally:
                connection.close()

    def test_phase12_to_phase13_upgrade_preserves_legacy_data(self) -> None:
        source = self.legacy_path
        self.assertTrue(source.exists())
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "upgrade.db"
            shutil.copy2(source, database_path)
            before = _snapshot(database_path)

            config = _config(_database_url(database_path))
            command.upgrade(config, "head")
            after = _snapshot(database_path)
            self.assertEqual(before, after)

            connection = sqlite3.connect(database_path)
            try:
                tables = _tables(database_path)
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

    def test_downgrade_and_reupgrade(self) -> None:
        source = self.legacy_path
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "downgrade.db"
            shutil.copy2(source, database_path)
            config = _config(_database_url(database_path))
            command.upgrade(config, "head")
            command.downgrade(config, "base")
            tables = _tables(database_path)
            for table in APPLICATION_TABLES:
                self.assertIn(table, tables)
            for table in PHASE12_TABLES + PHASE13_TABLES + PHASE14_TABLES + PHASE22_TABLES:
                self.assertNotIn(table, tables)

            before = _snapshot(database_path)
            command.upgrade(config, "head")
            after = _snapshot(database_path)
            self.assertEqual(before, after)
            command.check(config)

    def test_postgresql_ddl_compiles(self) -> None:
        from sqlalchemy.dialects import postgresql
        from sqlalchemy.schema import CreateTable

        dialect = postgresql.dialect()
        for table in Base.metadata.sorted_tables:
            compiled = str(CreateTable(table).compile(dialect=dialect))
            self.assertIn(f"CREATE TABLE {table.name}", compiled)
            self.assertNotIn("AUTOINCREMENT", compiled)


if __name__ == "__main__":
    unittest.main()