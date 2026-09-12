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


class Phase12MigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._ensure_clean_legacy_database()

    def _ensure_clean_legacy_database(self) -> None:
        db_path = ROOT / "arqau.db"
        connection = sqlite3.connect(db_path)
        try:
            for constraint in PHASE12_CHECK_CONSTRAINTS:
                connection.execute(
                    f"DROP INDEX IF EXISTS {constraint}"
                )
            for index in PHASE12_INDEXES:
                connection.execute(f"DROP INDEX IF EXISTS {index}")
            for table in PHASE12_TABLES:
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
            return {
                table: connection.execute(
                    f"SELECT * FROM {table} ORDER BY 1"
                ).fetchall()
                for table in APPLICATION_TABLES
                if table in existing_tables
            }
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
                self.assertEqual(
                    connection.execute("SELECT version_num FROM alembic_version").fetchone(),
                    ("20260911_0002",),
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
        source = ROOT / "arqau.db"
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
                self.assertEqual(
                    connection.execute("SELECT version_num FROM alembic_version").fetchone(),
                    ("20260911_0002",),
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
        source = ROOT / "arqau.db"
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
                for table in PHASE12_TABLES:
                    self.assertNotIn(table, tables)
            finally:
                connection.close()

    def test_upgrade_after_downgrade_works_again(self) -> None:
        source = ROOT / "arqau.db"
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
