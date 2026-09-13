"""Admin-only role and employer-membership management endpoints.

These exist so RBAC can be provisioned and tested via the API. They are
restricted to super_admin.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from pydantic import BaseModel

from app.database import get_db
from app.models import Employer, EmployerAdmin, ROLE_SUPER_ADMIN, User
from app.schemas.audit import AuditLogRead
from app.schemas.auth import UserResponse
from app.api.v1.auth import get_current_user
from app.core.authorization import get_employer_scope
from app.core.security import role_from_user
from app.services.audit_service import (
    EMPLOYER_ADMIN_ASSIGNED,
    USER_ROLE_CHANGED,
    list_audit_logs,
    record_audit_event,
    serialize_audit_log,
)

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_super_admin(current_user) -> None:
    if role_from_user(current_user) != ROLE_SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


class RoleAssignment(BaseModel):
    role: str


class EmployerAdminAssignment(BaseModel):
    user_id: str
    employer_id: str


@router.get("/audit-logs", response_model=list[AuditLogRead])
async def get_audit_logs(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    employer_id: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    role = role_from_user(current_user)
    if role == ROLE_SUPER_ADMIN:
        rows = await list_audit_logs(
            db,
            employer_id=employer_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            limit=limit,
            offset=offset,
        )
    elif role in ("employer_admin", "finance_manager"):
        scope = await get_employer_scope(current_user, db)
        if not scope:
            return []
        rows = await list_audit_logs(
            db,
            employer_ids=set(scope),
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            limit=limit,
            offset=offset,
        )
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return [serialize_audit_log(row) for row in rows]


@router.post("/users/{user_id}/role", response_model=UserResponse)
async def set_role(
    user_id: str,
    data: RoleAssignment,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_super_admin(current_user)
    if data.role not in ("employee", "employer_admin", "finance_manager", "super_admin"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    previous_role = user.role
    user.role = data.role
    await record_audit_event(
        db,
        actor_user_id=current_user.id,
        action=USER_ROLE_CHANGED,
        entity_type="user",
        entity_id=user.id,
        metadata={"previous_role": previous_role, "new_role": data.role},
    )
    await db.commit()
    await db.refresh(user)
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        is_verified=user.is_verified,
        is_active=user.is_active,
        created_at=user.created_at.isoformat() if user.created_at else "",
    )


@router.post("/employer-admins", status_code=status.HTTP_201_CREATED)
async def add_employer_admin(
    data: EmployerAdminAssignment,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_super_admin(current_user)
    user = await db.get(User, data.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    employer = await db.get(Employer, data.employer_id)
    if not employer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employer not found")
    existing = await db.execute(
        select(EmployerAdmin).where(
            EmployerAdmin.user_id == data.user_id,
            EmployerAdmin.employer_id == data.employer_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already an admin for this employer")
    membership = EmployerAdmin(user_id=data.user_id, employer_id=data.employer_id)
    db.add(membership)
    await db.flush()
    await record_audit_event(
        db,
        actor_user_id=current_user.id,
        employer_id=data.employer_id,
        action=EMPLOYER_ADMIN_ASSIGNED,
        entity_type="employer_admin",
        entity_id=membership.id,
        metadata={"user_id": data.user_id},
    )
    await db.commit()
    return {"detail": "Employer admin assigned"}