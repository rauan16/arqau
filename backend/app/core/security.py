from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.config import get_settings
from app.models import VALID_ROLES

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password[:72])


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except JWTError:
        return None


# ---------------------------------------------------------------------------
# Refresh token helpers
# ---------------------------------------------------------------------------

import hashlib
import secrets


def generate_refresh_token() -> str:
    """Return a cryptographically random plaintext refresh token."""
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    """Return the SHA-256 digest of a plaintext refresh token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_refresh_token(user_id: str, expires_delta: Optional[timedelta] = None) -> tuple[str, str, datetime]:
    """Return (plaintext_token, token_hash, expires_at).

    All datetimes are naive UTC to stay consistent with the rest of the
    codebase (models use datetime.utcnow).
    """
    plaintext = generate_refresh_token()
    token_hash = hash_refresh_token(plaintext)
    if expires_delta:
        expires_at = datetime.utcnow() + expires_delta
    else:
        expires_at = datetime.utcnow() + timedelta(days=settings.refresh_token_expire_days)
    return plaintext, token_hash, expires_at


def make_family_id() -> str:
    return secrets.token_urlsafe(24)


def role_from_user(user) -> str:
    """Safe role resolution. Legacy users without an explicit role map to employee."""
    role = getattr(user, "role", None)
    if role in VALID_ROLES:
        return role
    return "employee"