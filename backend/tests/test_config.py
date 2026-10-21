from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from app.config import (
    DEFAULT_DEVELOPMENT_SECRET_KEY,
    MIN_SECRET_ENTROPY,
    MIN_ACCESS_TOKEN_TTL,
    MAX_ACCESS_TOKEN_TTL,
    get_settings,
)
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
                "SECRET_KEY": "a" * MIN_SECRET_ENTROPY,
                "OPENAI_API_KEY": "server-key",
                "CORS_ORIGINS": "https://example.test",
            },
        ):
            settings = get_settings()

        self.assertTrue(settings.is_postgresql)
        self.assertEqual(settings.secret_key, "a" * MIN_SECRET_ENTROPY)

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

    def test_production_rejects_empty_secret(self) -> None:
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "production",
                "DATABASE_URL": "postgresql+asyncpg://user:password@localhost/arqau",
                "SECRET_KEY": "   ",
                "OPENAI_API_KEY": "server-key",
            },
        ):
            with self.assertRaises(ValidationError):
                get_settings()

    def test_production_rejects_placeholder_secret(self) -> None:
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "production",
                "DATABASE_URL": "postgresql+asyncpg://user:password@localhost/arqau",
                "SECRET_KEY": "arqau-secret-key-change-in-production",
                "OPENAI_API_KEY": "server-key",
            },
        ):
            with self.assertRaises(ValidationError):
                get_settings()

    def test_production_rejects_known_weak_secrets(self) -> None:
        weak_secrets = ["change-me", "secret", "secretkey", "dev-secret", "test-secret", "placeholder"]
        for weak in weak_secrets:
            with self.subTest(weak=weak):
                with patch.dict(
                    os.environ,
                    {
                        "APP_ENV": "production",
                        "DATABASE_URL": "postgresql+asyncpg://user:password@localhost/arqau",
                        "SECRET_KEY": weak,
                        "OPENAI_API_KEY": "server-key",
                    },
                ):
                    with self.assertRaises(ValidationError):
                        get_settings()

    def test_production_rejects_weak_secret_below_entropy(self) -> None:
        short_secret = "a" * (MIN_SECRET_ENTROPY - 1)
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "production",
                "DATABASE_URL": "postgresql+asyncpg://user:password@localhost/arqau",
                "SECRET_KEY": short_secret,
                "OPENAI_API_KEY": "server-key",
            },
        ):
            with self.assertRaises(ValidationError):
                get_settings()

    def test_production_accepts_valid_secret(self) -> None:
        valid_secret = "a" * MIN_SECRET_ENTROPY
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "production",
                "DATABASE_URL": "postgresql+asyncpg://user:password@localhost/arqau",
                "SECRET_KEY": valid_secret,
                "OPENAI_API_KEY": "server-key",
                "CORS_ORIGINS": "https://example.test",
            },
        ):
            settings = get_settings()
            self.assertEqual(settings.secret_key, valid_secret)

    def test_production_rejects_empty_issuer(self) -> None:
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "production",
                "DATABASE_URL": "postgresql+asyncpg://user:password@localhost/arqau",
                "SECRET_KEY": "a" * MIN_SECRET_ENTROPY,
                "OPENAI_API_KEY": "server-key",
                "JWT_ISSUER": "",
            },
        ):
            with self.assertRaises(ValidationError):
                get_settings()

    def test_production_rejects_whitespace_issuer(self) -> None:
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "production",
                "DATABASE_URL": "postgresql+asyncpg://user:password@localhost/arqau",
                "SECRET_KEY": "a" * MIN_SECRET_ENTROPY,
                "OPENAI_API_KEY": "server-key",
                "JWT_ISSUER": "   ",
            },
        ):
            with self.assertRaises(ValidationError):
                get_settings()

    def test_production_rejects_empty_audience(self) -> None:
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "production",
                "DATABASE_URL": "postgresql+asyncpg://user:password@localhost/arqau",
                "SECRET_KEY": "a" * MIN_SECRET_ENTROPY,
                "OPENAI_API_KEY": "server-key",
                "JWT_AUDIENCE": "",
            },
        ):
            with self.assertRaises(ValidationError):
                get_settings()

    def test_production_rejects_whitespace_audience(self) -> None:
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "production",
                "DATABASE_URL": "postgresql+asyncpg://user:password@localhost/arqau",
                "SECRET_KEY": "a" * MIN_SECRET_ENTROPY,
                "OPENAI_API_KEY": "server-key",
                "JWT_AUDIENCE": "   ",
            },
        ):
            with self.assertRaises(ValidationError):
                get_settings()

    def test_production_rejects_access_ttl_below_minimum(self) -> None:
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "production",
                "DATABASE_URL": "postgresql+asyncpg://user:password@localhost/arqau",
                "SECRET_KEY": "a" * MIN_SECRET_ENTROPY,
                "OPENAI_API_KEY": "server-key",
                "ACCESS_TOKEN_EXPIRE_MINUTES": "0",
            },
        ):
            with self.assertRaises(ValidationError):
                get_settings()

    def test_production_rejects_access_ttl_above_maximum(self) -> None:
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "production",
                "DATABASE_URL": "postgresql+asyncpg://user:password@localhost/arqau",
                "SECRET_KEY": "a" * MIN_SECRET_ENTROPY,
                "OPENAI_API_KEY": "server-key",
                "ACCESS_TOKEN_EXPIRE_MINUTES": str(MAX_ACCESS_TOKEN_TTL + 1),
            },
        ):
            with self.assertRaises(ValidationError):
                get_settings()

    def test_production_accepts_valid_access_ttl(self) -> None:
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "production",
                "DATABASE_URL": "postgresql+asyncpg://user:password@localhost/arqau",
                "SECRET_KEY": "a" * MIN_SECRET_ENTROPY,
                "OPENAI_API_KEY": "server-key",
                "CORS_ORIGINS": "https://example.test",
                "ACCESS_TOKEN_EXPIRE_MINUTES": "30",
            },
        ):
            settings = get_settings()
            self.assertEqual(settings.access_token_expire_minutes, 30)

    def test_production_rejects_sqlite(self) -> None:
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "production",
                "DATABASE_URL": "sqlite+aiosqlite:///./arqau.db",
                "SECRET_KEY": "a" * MIN_SECRET_ENTROPY,
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

