from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta

import httpx
import jwt as pyjwt
from sqlalchemy import text

from app.core.auth_rate_limit import _reset_all_limiters
from app.core.database import Base, configure_database, create_database
from app.config import get_settings
from app.database import get_db
from app.main import app
from app.models import RefreshToken, User

os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("OPENAI_API_KEY", "test-key")


class Phase13AuthTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        _reset_all_limiters()
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "auth.db"
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

    # -- AUTH -----------------------------------------------------------

    async def test_register_issues_access_and_refresh(self) -> None:
        payload = await self._register("auth1@example.com", name="A")
        self.assertTrue(payload["access_token"])
        self.assertTrue(payload["refresh_token"])
        self.assertEqual(payload["role"], "employee")
        self.assertEqual(payload["token_type"], "bearer")

        async with self.sessions() as session:
            rows = (await session.execute(text("SELECT COUNT(*) FROM refresh_tokens"))).scalar_one()
            self.assertEqual(rows, 1)
            stored = (await session.execute(text("SELECT token_hash, family_id, revoked_at FROM refresh_tokens"))).first()
            self.assertTrue(stored.token_hash)
            self.assertFalse(stored.token_hash.startswith(payload["refresh_token"]))
            self.assertIsNotNone(stored.family_id)
            self.assertIsNone(stored.revoked_at)

    async def test_login_issues_valid_tokens(self) -> None:
        await self._register("auth2@example.com", name="B")
        payload = await self._login("auth2@example.com")
        self.assertTrue(payload["access_token"])
        self.assertTrue(payload["refresh_token"])

    async def test_invalid_login_rejected(self) -> None:
        await self._register("auth3@example.com", name="C")
        response = await self.client.post("/auth/login", json={"email": "auth3@example.com", "password": "wrong"})
        self.assertEqual(response.status_code, 401)

    async def test_invalid_access_token_returns_401(self) -> None:
        response = await self.client.get("/auth/me", headers={"Authorization": "Bearer not-a-token"})
        self.assertEqual(response.status_code, 401)

    async def test_refresh_rotates_token_and_old_cannot_be_reused(self) -> None:
        payload = await self._register("auth4@example.com", name="D")
        old_refresh = payload["refresh_token"]

        refresh = await self.client.post("/auth/refresh", json={"refresh_token": old_refresh})
        self.assertEqual(refresh.status_code, 200, refresh.text)
        new_payload = refresh.json()
        self.assertNotEqual(new_payload["refresh_token"], old_refresh)

        # Old refresh token must be rejected after rotation.
        reuse = await self.client.post("/auth/refresh", json={"refresh_token": old_refresh})
        self.assertEqual(reuse.status_code, 401)

        # Reuse of a rotated token revokes the whole family, so the rotated
        # successor is also rejected (fail-closed).
        again = await self.client.post("/auth/refresh", json={"refresh_token": new_payload["refresh_token"]})
        self.assertEqual(again.status_code, 401)

    async def test_revoked_refresh_rejected(self) -> None:
        payload = await self._register("auth5@example.com", name="E")
        logout = await self.client.post("/auth/logout", json={"refresh_token": payload["refresh_token"]})
        self.assertEqual(logout.status_code, 200)
        reuse = await self.client.post("/auth/refresh", json={"refresh_token": payload["refresh_token"]})
        self.assertEqual(reuse.status_code, 401)

    async def test_logout_all_revokes_sessions(self) -> None:
        payload = await self._register("auth6@example.com", name="F")
        headers = {"Authorization": f"Bearer {payload['access_token']}"}
        logout_all = await self.client.post("/auth/logout-all", headers=headers)
        self.assertEqual(logout_all.status_code, 200)
        reuse = await self.client.post("/auth/refresh", json={"refresh_token": payload["refresh_token"]})
        self.assertEqual(reuse.status_code, 401)

    async def test_expired_refresh_rejected(self) -> None:
        payload = await self._register("auth7@example.com", name="G")
        async with self.sessions() as session:
            await session.execute(
                text(
                    "UPDATE refresh_tokens SET expires_at = '2000-01-01 00:00:00' "
                    "WHERE user_id = :uid"
                ),
                {"uid": payload["user_id"]},
            )
            await session.commit()
        reuse = await self.client.post("/auth/refresh", json={"refresh_token": payload["refresh_token"]})
        self.assertEqual(reuse.status_code, 401)

    async def test_plaintext_refresh_not_stored(self) -> None:
        payload = await self._register("auth8@example.com", name="H")
        async with self.sessions() as session:
            row = (await session.execute(text("SELECT token_hash FROM refresh_tokens"))).first()
            self.assertNotIn(payload["refresh_token"], row.token_hash)
            self.assertEqual(len(row.token_hash), 64)

    # -- TTL & CLAIMS HARDENING ----------------------------------------

    async def test_render_config_access_ttl_thirty_minutes(self) -> None:
        """Render configuration should specify 30-minute access TTL."""
        import yaml
        render_path = Path(__file__).resolve().parents[1] / "render.yaml"
        with open(render_path) as f:
            render_config = yaml.safe_load(f)
        env_vars = {}
        for item in render_config["services"][0]["envVars"]:
            if "value" in item:
                env_vars[item["key"]] = item["value"]
        self.assertEqual(env_vars.get("ACCESS_TOKEN_EXPIRE_MINUTES"), "30")

    async def test_access_token_expires_according_to_configured_ttl(self) -> None:
        """Newly issued access tokens should expire according to configured TTL."""
        from app.core.security import create_access_token, decode_access_token
        from app.config import get_settings

        settings = get_settings()
        # Default is 30 minutes
        token = create_access_token({"sub": "test-user", "role": "employee"})
        payload = decode_access_token(token)
        self.assertIn("exp", payload)
        self.assertIn("iat", payload)

        # exp should be roughly 30 minutes from now
        exp_dt = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        iat_dt = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
        delta = exp_dt - iat_dt
        self.assertGreaterEqual(delta, timedelta(minutes=29))
        self.assertLessEqual(delta, timedelta(minutes=31))

    async def test_access_token_contains_valid_iat(self) -> None:
        """Newly issued access tokens should contain a valid iat claim."""
        from app.core.security import create_access_token, decode_access_token

        before = datetime.now(timezone.utc)
        token = create_access_token({"sub": "test-user", "role": "employee"})
        after = datetime.now(timezone.utc)

        payload = decode_access_token(token)
        self.assertIn("iat", payload)
        iat_dt = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
        self.assertGreaterEqual(iat_dt, before - timedelta(seconds=2))
        self.assertLessEqual(iat_dt, after + timedelta(seconds=2))

    async def test_tokens_without_iss_aud_rejected(self) -> None:
        """Tokens without iss and aud claims should be rejected."""
        from app.core.security import decode_access_token
        from app.config import get_settings

        settings = get_settings()
        now = datetime.now(timezone.utc)
        exp = now + timedelta(minutes=30)
        # Token without iss and aud
        token = pyjwt.encode(
            {"sub": "legacy-user", "role": "employee", "exp": exp},
            settings.secret_key,
            algorithm=settings.algorithm,
        )
        payload = decode_access_token(token)
        self.assertIsNone(payload)

    async def test_inactive_user_rejected_on_auth_me(self) -> None:
        """Inactive users should receive 401 on /auth/me."""
        payload = await self._register("inactive@example.com", name="Inactive")
        access_token = payload["access_token"]

        # Deactivate the user
        async with self.sessions() as session:
            user = await session.get(User, payload["user_id"])
            user.is_active = False
            await session.commit()

        # Try to access /auth/me with inactive user's token
        response = await self.client.get("/auth/me", headers={"Authorization": f"Bearer {access_token}"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Inactive account")

    async def test_inactive_user_cannot_refresh(self) -> None:
        """Inactive users should not be able to refresh tokens."""
        payload = await self._register("inactive2@example.com", name="Inactive2")
        refresh_token = payload["refresh_token"]

        # Deactivate the user
        async with self.sessions() as session:
            user = await session.get(User, payload["user_id"])
            user.is_active = False
            await session.commit()

        # Try to refresh with inactive user's refresh token
        response = await self.client.post("/auth/refresh", json={"refresh_token": refresh_token})
        self.assertEqual(response.status_code, 401)

    async def test_refresh_rotation_still_works(self) -> None:
        """Existing refresh rotation should continue to work after changes."""
        payload = await self._register("rotation@example.com", name="Rotation")
        old_refresh = payload["refresh_token"]

        refresh = await self.client.post("/auth/refresh", json={"refresh_token": old_refresh})
        self.assertEqual(refresh.status_code, 200, refresh.text)
        new_payload = refresh.json()
        self.assertNotEqual(new_payload["refresh_token"], old_refresh)
        self.assertIn("access_token", new_payload)
        # Verify iat in new access token by decoding it
        decoded = pyjwt.decode(new_payload["access_token"], options={"verify_signature": False})
        self.assertIn("iat", decoded)

    async def test_invalid_signature_and_expired_tokens_rejected(self) -> None:
        """Invalid signatures and expired tokens should remain rejected."""
        from app.core.security import decode_access_token
        from app.config import get_settings

        settings = get_settings()

        # Invalid signature
        bad_token = pyjwt.encode(
            {"sub": "test", "role": "employee", "exp": datetime.now(timezone.utc) + timedelta(minutes=30)},
            "wrong-secret",
            algorithm=settings.algorithm,
        )
        self.assertIsNone(decode_access_token(bad_token))

        # Expired token
        expired_token = pyjwt.encode(
            {"sub": "test", "role": "employee", "exp": datetime.now(timezone.utc) - timedelta(minutes=5)},
            settings.secret_key,
            algorithm=settings.algorithm,
        )
        self.assertIsNone(decode_access_token(expired_token))

    # -- ISS/AUD CLAIMS ------------------------------------------------

    async def test_new_token_includes_iss_aud_iat_exp(self) -> None:
        """Newly issued access tokens should include iss, aud, iat, and exp."""
        from app.core.security import create_access_token
        from app.config import get_settings

        settings = get_settings()
        token = create_access_token({"sub": "test-user", "role": "employee"})
        decoded = pyjwt.decode(token, options={"verify_signature": False})
        self.assertEqual(decoded["iss"], settings.jwt_issuer)
        self.assertEqual(decoded["aud"], settings.jwt_audience)
        self.assertIn("iat", decoded)
        self.assertIn("exp", decoded)

    async def test_valid_new_format_token_accepted(self) -> None:
        """Valid new-format token with correct iss and aud should be accepted."""
        from app.core.security import create_access_token, decode_access_token

        token = create_access_token({"sub": "test-user", "role": "employee"})
        payload = decode_access_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["sub"], "test-user")

    async def test_incorrect_issuer_rejected(self) -> None:
        """Token with incorrect issuer should be rejected."""
        from app.core.security import decode_access_token
        from app.config import get_settings

        settings = get_settings()
        # Create token with wrong issuer
        now = datetime.now(timezone.utc)
        exp = now + timedelta(minutes=30)
        token = pyjwt.encode(
            {"sub": "test-user", "role": "employee", "exp": exp, "iat": now, "iss": "wrong-issuer", "aud": settings.jwt_audience},
            settings.secret_key,
            algorithm=settings.algorithm,
        )
        self.assertIsNone(decode_access_token(token))

    async def test_incorrect_audience_rejected(self) -> None:
        """Token with incorrect audience should be rejected."""
        from app.core.security import decode_access_token
        from app.config import get_settings

        settings = get_settings()
        # Create token with wrong audience
        now = datetime.now(timezone.utc)
        exp = now + timedelta(minutes=30)
        token = pyjwt.encode(
            {"sub": "test-user", "role": "employee", "exp": exp, "iat": now, "iss": settings.jwt_issuer, "aud": "wrong-audience"},
            settings.secret_key,
            algorithm=settings.algorithm,
        )
        self.assertIsNone(decode_access_token(token))

    async def test_missing_only_iss_rejected(self) -> None:
        """Token with aud but missing iss should be rejected."""
        from app.core.security import decode_access_token
        from app.config import get_settings

        settings = get_settings()
        # Create token with aud but no iss
        now = datetime.now(timezone.utc)
        exp = now + timedelta(minutes=30)
        token = pyjwt.encode(
            {"sub": "test-user", "role": "employee", "exp": exp, "iat": now, "aud": settings.jwt_audience},
            settings.secret_key,
            algorithm=settings.algorithm,
        )
        self.assertIsNone(decode_access_token(token))

    async def test_missing_only_aud_rejected(self) -> None:
        """Token with iss but missing aud should be rejected."""
        from app.core.security import decode_access_token
        from app.config import get_settings

        settings = get_settings()
        # Create token with iss but no aud
        now = datetime.now(timezone.utc)
        exp = now + timedelta(minutes=30)
        token = pyjwt.encode(
            {"sub": "test-user", "role": "employee", "exp": exp, "iat": now, "iss": settings.jwt_issuer},
            settings.secret_key,
            algorithm=settings.algorithm,
        )
        self.assertIsNone(decode_access_token(token))

    async def test_token_missing_iss_rejected(self) -> None:
        """Token with aud but missing iss should be rejected."""
        from app.core.security import decode_access_token
        from app.config import get_settings

        settings = get_settings()
        now = datetime.now(timezone.utc)
        exp = now + timedelta(minutes=30)
        token = pyjwt.encode(
            {"sub": "test-user", "role": "employee", "exp": exp, "iat": now, "aud": settings.jwt_audience},
            settings.secret_key,
            algorithm=settings.algorithm,
        )
        self.assertIsNone(decode_access_token(token))

    async def test_token_missing_aud_rejected(self) -> None:
        """Token with iss but missing aud should be rejected."""
        from app.core.security import decode_access_token
        from app.config import get_settings

        settings = get_settings()
        now = datetime.now(timezone.utc)
        exp = now + timedelta(minutes=30)
        token = pyjwt.encode(
            {"sub": "test-user", "role": "employee", "exp": exp, "iat": now, "iss": settings.jwt_issuer},
            settings.secret_key,
            algorithm=settings.algorithm,
        )
        self.assertIsNone(decode_access_token(token))

    async def test_token_without_iss_aud_rejected(self) -> None:
        """Token with neither iss nor aud should be rejected."""
        from app.core.security import decode_access_token
        from app.config import get_settings

        settings = get_settings()
        now = datetime.now(timezone.utc)
        exp = now + timedelta(minutes=30)
        token = pyjwt.encode(
            {"sub": "test-user", "role": "employee", "exp": exp, "iat": now},
            settings.secret_key,
            algorithm=settings.algorithm,
        )
        self.assertIsNone(decode_access_token(token))

    async def test_expired_token_rejected(self) -> None:
        """Expired token should be rejected."""
        from app.core.security import decode_access_token
        from app.config import get_settings

        settings = get_settings()
        now = datetime.now(timezone.utc)
        exp = now - timedelta(minutes=5)
        expired_token = pyjwt.encode(
            {"sub": "test-user", "role": "employee", "exp": exp, "iat": now, "iss": settings.jwt_issuer, "aud": settings.jwt_audience},
            settings.secret_key,
            algorithm=settings.algorithm,
        )
        self.assertIsNone(decode_access_token(expired_token))

    async def test_invalid_signature_rejected(self) -> None:
        """Invalid signature should be rejected."""
        from app.core.security import decode_access_token
        from app.config import get_settings

        settings = get_settings()
        now = datetime.now(timezone.utc)
        exp = now + timedelta(minutes=30)

        # New format with bad signature
        new_bad = pyjwt.encode(
            {"sub": "test", "role": "employee", "exp": exp, "iat": now, "iss": settings.jwt_issuer, "aud": settings.jwt_audience},
            "wrong-secret",
            algorithm=settings.algorithm,
        )
        self.assertIsNone(decode_access_token(new_bad))

    async def test_unsupported_algorithm_rejected(self) -> None:
        """Unsupported JWT algorithm should be rejected."""
        from app.core.security import decode_access_token
        from app.config import get_settings

        settings = get_settings()
        now = datetime.now(timezone.utc)
        exp = now + timedelta(minutes=30)

        # Try to use "none" algorithm (should be rejected as we only allow HS256)
        none_token = pyjwt.encode(
            {"sub": "test", "role": "employee", "exp": exp, "iat": now, "iss": settings.jwt_issuer, "aud": settings.jwt_audience},
            "",
            algorithm="none",
        )
        self.assertIsNone(decode_access_token(none_token))


if __name__ == "__main__":
    unittest.main()