from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import httpx
from sqlalchemy import text

from app.core.database import Base, configure_database, create_database
from app.config import get_settings
from app.database import get_db
from app.main import app
from app.models import RefreshToken

os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("OPENAI_API_KEY", "test-key")


class Phase13AuthTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
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


if __name__ == "__main__":
    unittest.main()