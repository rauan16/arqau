"""Reusable audit-service for ARQAU Phase 1.4.

Records security and business actions to the AuditLog table. The helper is
intentionally small and side-effect free: it appends an AuditLog row and lets
the caller's transaction commit (or roll back) naturally.

Sensitive values are never written: passwords, JWTs, refresh tokens, API
keys, and full request bodies are excluded by the caller via metadata.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# AUTH
LOGIN_SUCCESS = "LOGIN_SUCCESS"
LOGIN_FAILED = "LOGIN_FAILED"
REFRESH_ROTATED = "REFRESH_ROTATED"
LOGOUT = "LOGOUT"
LOGOUT_ALL = "LOGOUT_ALL"

# DOMAIN
EMPLOYER_CREATED = "EMPLOYER_CREATED"
EMPLOYEE_CREATED = "EMPLOYEE_CREATED"
EMPLOYMENT_CREATED = "EMPLOYMENT_CREATED"
SALARY_PROFILE_CREATED = "SALARY_PROFILE_CREATED"
SALARY_PROFILE_UPDATED = "SALARY_PROFILE_UPDATED"
USER_ROLE_CHANGED = "USER_ROLE_CHANGED"
EMPLOYER_ADMIN_ASSIGNED = "EMPLOYER_ADMIN_ASSIGNED"
EMPLOYER_ADMIN_REMOVED = "EMPLOYER_ADMIN_REMOVED"

# EWA
EWA_POLICY_CREATED = "EWA_POLICY_CREATED"
EWA_POLICY_UPDATED = "EWA_POLICY_UPDATED"

# EWA legacy flow
USER_REQUESTED_WITHDRAWAL = "USER_REQUESTED_WITHDRAWAL"

# EWA Phase 2.4 lifecycle
WITHDRAWAL_APPROVED = "WITHDRAWAL_APPROVED"
WITHDRAWAL_REJECTED = "WITHDRAWAL_REJECTED"
WITHDRAWAL_CANCELLED = "WITHDRAWAL_CANCELLED"
WITHDRAWAL_PAID = "WITHDRAWAL_PAID"

# Sensitive metadata keys that are always stripped, even if a caller passes
# them by mistake.
BLOCKED_METADATA_KEYS = frozenset(
    {
        "password",
        "hashed_password",
        "refresh_token",
        "access_token",
        "token",
        "secret",
        "api_key",
        "openai_api_key",
        "authorization",
        "cookie",
        "session",
    }
)


def _sanitize_json(value: Any) -> Any:
    """Return a JSON-safe value without sensitive fields."""
    if value is None:
        return None
    if isinstance(value, dict):
        return {
            str(key): _sanitize_json(item)
            for key, item in value.items()
            if str(key).lower() not in BLOCKED_METADATA_KEYS
        }
    if isinstance(value, (list, tuple, set)):
        return [_sanitize_json(item) for item in value]
    if isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "__dict__"):
        return {
            str(key): _sanitize_json(item)
            for key, item in vars(value).items()
            if not str(key).startswith("_") and not callable(item)
        }
    return str(value)


def _sanitize_metadata(metadata: Optional[dict]) -> Optional[dict]:
    """Return a copy of metadata with sensitive keys removed."""
    sanitized = _sanitize_json(metadata)
    return sanitized if isinstance(sanitized, dict) and sanitized else None


def _coerce_json(value: Any) -> Any:
    """Best-effort JSON-safe coercion for before/after snapshots."""
    return _sanitize_json(value)


async def record_audit_event(
    db: AsyncSession,
    *,
    actor_user_id: Optional[str] = None,
    employer_id: Optional[str] = None,
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    request_id: Optional[str] = None,
    metadata: Optional[dict] = None,
    before_data: Any = None,
    after_data: Any = None,
) -> AuditLog:
    """Insert a single AuditLog row within the caller's transaction."""
    row = AuditLog(
        id=str(uuid.uuid4()),
        actor_user_id=actor_user_id,
        employer_id=employer_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        request_id=request_id,
        details=_sanitize_metadata(metadata),
        before_data=_coerce_json(before_data),
        after_data=_coerce_json(after_data),
        created_at=datetime.utcnow(),
    )
    db.add(row)
    await db.flush()
    return row


async def list_audit_logs(
    db: AsyncSession,
    *,
    employer_ids: Optional[set[str]] = None,
    employer_id: Optional[str] = None,
    actor_user_id: Optional[str] = None,
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditLog]:
    """Read audit logs with optional filters."""
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
    if employer_ids is not None:
        stmt = stmt.where(AuditLog.employer_id.in_(employer_ids))
    elif employer_id is not None:
        stmt = stmt.where(AuditLog.employer_id == employer_id)
    if actor_user_id is not None:
        stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
    if action is not None:
        stmt = stmt.where(AuditLog.action == action)
    if entity_type is not None:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


def serialize_audit_log(row: AuditLog) -> dict:
    """Return the safe audit fields exposed by the read API."""
    return {
        "id": row.id,
        "actor_user_id": row.actor_user_id,
        "employer_id": row.employer_id,
        "action": row.action,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "request_id": row.request_id,
        "details": _sanitize_json(row.details),
        "before_data": _sanitize_json(row.before_data),
        "after_data": _sanitize_json(row.after_data),
        "created_at": row.created_at,
    }
