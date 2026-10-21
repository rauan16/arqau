"""Production configuration guard for backend/render.yaml (Phase 4.1).

Regression guard for the Phase 4 audit findings:

- P1-1: CORS_ORIGINS contained http://localhost:3000, which app/config.py
  rejects when APP_ENV=production (the service would refuse to start).
- P1-2: OPENAI_MODEL was gpt-4o-mini instead of the OpenRouter model that
  was verified with a real request in Phase 3.4.

Fully offline: no network, no OpenRouter request, no real secrets. Variables
declared with `sync: false` are represented by clearly-fake placeholders that
exist only to exercise the validation logic.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from app.config import (
    MIN_SECRET_ENTROPY,
    Settings,
    _validate_cors_origins,
    get_settings,
)
from app.services.ai_copilot import (
    OpenAICopilotProvider,
    get_copilot_provider,
    reset_production_provider,
)

RENDER_PATH = Path(__file__).resolve().parents[1] / "render.yaml"

# The OpenRouter model verified with a real request in Phase 3.4.
VERIFIED_OPENAI_MODEL = "deepseek/deepseek-v4.1-flash-1017"

# The Vercel production frontend origin (Vercel project name: "arqau").
PRODUCTION_FRONTEND_ORIGIN = "https://arqau.vercel.app"

# Render generates a base64-encoded 256-bit value for `generateValue: true`,
# i.e. 44 characters, which satisfies the production entropy requirement.
RENDER_GENERATED_SECRET_LENGTH = 44

# Allowed `runtime` values for a web service, per the Render Blueprint JSON
# schema (https://render.com/schema/render.yaml.json -> definitions.runtime).
# The Python *version* is pinned separately via .python-version / runtime.txt.
ALLOWED_RENDER_RUNTIMES = (
    "docker",
    "elixir",
    "go",
    "image",
    "node",
    "python",
    "ruby",
    "rust",
    "static",
)


def _load_render_config() -> dict:
    with open(RENDER_PATH) as handle:
        return yaml.safe_load(handle)


def _env_vars_by_key() -> dict[str, dict]:
    return {item["key"]: item for item in _load_render_config()["services"][0]["envVars"]}


class RenderBlueprintTests(unittest.TestCase):
    def test_blueprint_declares_single_python_web_service(self) -> None:
        config = _load_render_config()
        self.assertEqual(len(config["services"]), 1)
        service = config["services"][0]
        self.assertEqual(service["type"], "web")
        self.assertEqual(service["name"], "arqau-backend")
        self.assertEqual(service["runtime"], "python")
        # Migrations must run before the server starts.
        self.assertIn("alembic upgrade head", service["startCommand"])

    def test_runtime_is_a_schema_valid_value(self) -> None:
        """The Render Blueprint schema only accepts a fixed set of runtimes."""
        service = _load_render_config()["services"][0]
        self.assertIn(service["runtime"], ALLOWED_RENDER_RUNTIMES)

    def test_deprecated_env_key_is_absent(self) -> None:
        """`env` was replaced by `runtime` and is not in the Blueprint schema."""
        service = _load_render_config()["services"][0]
        self.assertNotIn("env", service)

    def test_python_version_is_pinned_outside_the_blueprint(self) -> None:
        """The Python version comes from .python-version / runtime.txt."""
        backend_root = RENDER_PATH.parent
        python_version_file = backend_root / ".python-version"
        self.assertTrue(python_version_file.exists())
        version = python_version_file.read_text().strip()
        self.assertTrue(version.startswith("3.12"), version)

    def test_app_env_is_production(self) -> None:
        self.assertEqual(_env_vars_by_key()["APP_ENV"].get("value"), "production")

    # -- CORS -------------------------------------------------------------

    def test_cors_origins_pass_production_validation(self) -> None:
        value = _env_vars_by_key()["CORS_ORIGINS"].get("value", "")
        errors = _validate_cors_origins(value, "production")
        self.assertEqual(errors, [], f"production CORS origins rejected: {errors}")

    def test_cors_origins_contain_production_frontend_origin(self) -> None:
        value = _env_vars_by_key()["CORS_ORIGINS"].get("value", "")
        self.assertIn(PRODUCTION_FRONTEND_ORIGIN, value)

    def test_cors_origins_exclude_localhost_and_loopback(self) -> None:
        value = _env_vars_by_key()["CORS_ORIGINS"].get("value", "")
        for origin in value.split(","):
            self.assertNotIn("localhost", origin)
            self.assertNotIn("127.0.0.1", origin)
            self.assertNotIn("::1", origin)

    # -- Model ------------------------------------------------------------

    def test_openai_model_is_the_phase34_verified_model(self) -> None:
        self.assertEqual(
            _env_vars_by_key()["OPENAI_MODEL"].get("value"),
            VERIFIED_OPENAI_MODEL,
        )

    def test_provider_accepts_the_configured_model_identifier(self) -> None:
        """The provider stores the model id verbatim; no network call happens."""
        provider = OpenAICopilotProvider(
            api_key="sk-or-test-placeholder",
            model=VERIFIED_OPENAI_MODEL,
        )
        self.assertEqual(provider.model, VERIFIED_OPENAI_MODEL)
        self.assertEqual(provider.name, "openrouter")
        self.assertTrue(provider.is_configured)

    def test_openai_model_flows_from_environment_into_the_provider(self) -> None:
        """env -> Settings.openai_model -> OpenAICopilotProvider.model."""
        with patch.dict(
            os.environ,
            {"OPENAI_MODEL": VERIFIED_OPENAI_MODEL, "OPENAI_API_KEY": "sk-or-test-placeholder"},
        ):
            settings = get_settings()
            self.assertEqual(settings.openai_model, VERIFIED_OPENAI_MODEL)
            reset_production_provider()
            try:
                provider = get_copilot_provider()
            finally:
                reset_production_provider()
        self.assertEqual(provider.model, VERIFIED_OPENAI_MODEL)

    # -- Secrets ----------------------------------------------------------

    def test_secrets_are_not_hardcoded_in_the_blueprint(self) -> None:
        env = _env_vars_by_key()
        for key in ("OPENAI_API_KEY", "DATABASE_URL"):
            self.assertNotIn("value", env[key], f"{key} must not be hardcoded")
            # `sync: false` prompts for the value in the Render Dashboard.
            self.assertIn("sync", env[key], f"{key} must be set manually")
            self.assertIs(env[key]["sync"], False, f"{key} must use sync: false")
        # SECRET_KEY must never carry a literal value in the repository.
        self.assertNotIn("value", env["SECRET_KEY"])
        self.assertIs(env["SECRET_KEY"].get("generateValue"), True)

    def test_render_generated_secret_length_meets_entropy_requirement(self) -> None:
        self.assertGreaterEqual(
            RENDER_GENERATED_SECRET_LENGTH, MIN_SECRET_ENTROPY
        )

    # -- Whole-environment validation -------------------------------------

    def test_declared_production_environment_validates(self) -> None:
        """The declared production env must pass app/config.py validation."""
        env = _env_vars_by_key()
        settings = Settings(
            environment="production",
            openai_api_key="sk-or-test-placeholder",
            openai_model=env["OPENAI_MODEL"]["value"],
            secret_key="f" * MIN_SECRET_ENTROPY,
            database_url="postgresql+asyncpg://user:pass@localhost/arqau",
            cors_origins=env["CORS_ORIGINS"]["value"],
        )
        self.assertTrue(settings.is_postgresql)
        self.assertEqual(settings.cors_origins_list, [PRODUCTION_FRONTEND_ORIGIN])
        self.assertEqual(settings.openai_model, VERIFIED_OPENAI_MODEL)


if __name__ == "__main__":
    unittest.main()
