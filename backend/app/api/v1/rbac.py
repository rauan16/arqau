"""Admin-only role and employer-membership management endpoints.

These exist so RBAC can be provisioned and tested via the API. They are
restricted to super_admin.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from pydantic import BaseModel

from app.database import get_db
from app.models import User, EmployerAdmin, Employer, ROLE_SUPER_ADMIN
from app.schemas.auth import UserResponse
from app.api.v1.auth import get_current_user
from app.core.security import role_from_user

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_super_admin(current_user) -> None:
    if role_from_user(current_user) != ROLE_SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")


class RoleAssignment(BaseModel):
    role: str


class EmployerAdminAssignment(BaseModel):
    user_id: str
    employer_id: str


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
    user.role = data.role
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
    db.add(EmployerAdmin(user_id=data.user_id, employer_id=data.employer_id))
    await db.commit()
    return {"detail": "Employer admin assigned"}