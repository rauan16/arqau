from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from app.config import DEFAULT_DEVELOPMENT_SECRET_KEY, get_settings
from app.core.database import normalize_database_url


class ConfigurationTests(unittest.TestCase):
    def test_development_allows_sqlite_and_uses_non_production_secret(self) -> None:
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "development",
                "DATABASE_URL": "sqlite+aiosqlite:///./development.db",
                "SECRET_KEY": "",
                "OPENAI_API_KEY": "",
            },
        ):
            settings = get_settings()

        self.assertEqual(settings.environment, "development")
        self.assertEqual(settings.database_url, "sqlite+aiosqlite:///./development.db")
        self.assertEqual(settings.secret_key, DEFAULT_DEVELOPMENT_SECRET_KEY)
        self.assertFalse(settings.is_postgresql)

    def test_testing_allows_temporary_sqlite(self) -> None:
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "testing",
                "DATABASE_URL": "sqlite+aiosqlite:///./test.db",
                "SECRET_KEY": "test-secret",
                "OPENAI_API_KEY": "test-key",
            },
        ):
            settings = get_settings()

        self.assertEqual(settings.environment, "testing")
        self.assertEqual(settings.database_url, "sqlite+aiosqlite:///./test.db")

    def test_production_requires_postgresql_and_server_secrets(self) -> None:
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "production",
                "DATABASE_URL": "postgresql+asyncpg://user:password@localhost/arqau",
                "SECRET_KEY": "production-secret",
                "OPENAI_API_KEY": "server-key",
            },
        ):
            settings = get_settings()

        self.assertTrue(settings.is_postgresql)
        self.assertEqual(settings.secret_key, "production-secret")

    def test_production_rejects_missing_secret(self) -> None:
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "production",
                "DATABASE_URL": "postgresql+asyncpg://user:password@localhost/arqau",
                "SECRET_KEY": "",
                "OPENAI_API_KEY": "server-key",
            },
        ):
            with self.assertRaises(ValidationError):
                get_settings()

    def test_production_rejects_sqlite(self) -> None:
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "production",
                "DATABASE_URL": "sqlite+aiosqlite:///./arqau.db",
                "SECRET_KEY": "production-secret",
                "OPENAI_API_KEY": "server-key",
            },
        ):
            with self.assertRaises(ValidationError):
                get_settings()

    def test_empty_cors_origins_are_filtered(self) -> None:
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "development",
                "DATABASE_URL": "sqlite+aiosqlite:///./arqau.db",
                "CORS_ORIGINS": "http://localhost:3000, ,https://example.test",
            },
        ):
            self.assertEqual(
                get_settings().cors_origins_list,
                ["http://localhost:3000", "https://example.test"],
            )

    def test_postgres_url_normalization(self) -> None:
        self.assertEqual(
            normalize_database_url("postgres://user:password@localhost/arqau"),
            "postgresql+asyncpg://user:password@localhost/arqau",
        )
        self.assertEqual(
            normalize_database_url("postgresql://user:password@localhost/arqau"),
            "postgresql+asyncpg://user:password@localhost/arqau",
        )


if __name__ == "__main__":
    unittest.main()
