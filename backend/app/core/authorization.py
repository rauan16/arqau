"""Reusable authorization dependencies for ARQAU Phase 1.3.

Rules:
- super_admin: unrestricted platform scope.
- employer_admin: scoped to employers in their EmployerAdmin rows.
- finance_manager: scoped to employers in their EmployerAdmin rows, read-only
  finance operations only. Never granted mutation permissions automatically.
- employee: own Employee/Employment/SalaryProfile only.

Never trust client-provided employer_id. Scope is derived server-side from the
authenticated user.
"""

from __future__ import annotations

from typing import Optional, Sequence

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import get_current_user
from app.database import get_db
from app.models import (
    DEFAULT_ROLE,
    ROLE_EMPLOYEE,
    ROLE_EMPLOYER_ADMIN,
    ROLE_FINANCE_MANAGER,
    ROLE_SUPER_ADMIN,
    Employer,
    EmployerAdmin,
    Employee,
    Employment,
    SalaryProfile,
    User,
)
from app.core.security import role_from_user


def _role(user: User) -> str:
    return role_from_user(user)


def is_super_admin(user: User) -> bool:
    return _role(user) == ROLE_SUPER_ADMIN


def is_employer_admin(user: User) -> bool:
    """A user is an employer admin if their declared role is employer_admin
    OR they have at least one EmployerAdmin membership row. The membership
    table is the source of truth for scope; the role flag is a compatible
    marker."""
    return _role(user) == ROLE_EMPLOYER_ADMIN


def is_finance_manager(user: User) -> bool:
    return _role(user) == ROLE_FINANCE_MANAGER


def is_employee(user: User) -> bool:
    return _role(user) == ROLE_EMPLOYEE


def has_employer_membership(user: User) -> bool:
    """True if the user has any EmployerAdmin membership row (scoped admin)."""
    return bool(getattr(user, "_employer_membership", False))


async def get_employer_scope(user: User, db: AsyncSession) -> list[str]:
    """Return the list of employer ids the user is authorized to operate on.

    super_admin returns an empty list meaning "unrestricted" (caller must
    check is_super_admin separately). All other roles return their explicit
    employer membership scope. A user with no membership has no scope.
    """
    if is_super_admin(user):
        return []
    result = await db.execute(
        select(EmployerAdmin.employer_id).where(EmployerAdmin.user_id == user.id)
    )
    return list(result.scalars().all())


async def require_roles(user: User, db: AsyncSession, *allowed_roles: str) -> None:
    """Raise 403 unless the user's resolved role is in allowed_roles."""
    role = _role(user)
    if role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )


async def _user_has_scope(user: User, db: AsyncSession) -> bool:
    """True if the user is a member of at least one employer (scoped admin)."""
    if is_super_admin(user):
        return True
    result = await db.execute(
        select(EmployerAdmin.id).where(EmployerAdmin.user_id == user.id).limit(1)
    )
    return result.scalar_one_or_none() is not None


async def assert_employer_access(user: User, db: AsyncSession, employer_id: str) -> Employer:
    """Return the Employer if the user may access it, else raise.

    - super_admin: allowed.
    - employer_admin / finance_manager: must be a member of that employer.
    - employee: denied (employees do not have employer admin scope).
    """
    employer = await db.get(Employer, employer_id)
    if not employer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employer not found")
    if is_super_admin(user):
        return employer
    scope = await get_employer_scope(user, db)
    if employer_id in scope:
        return employer
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employer not found")


async def assert_employment_access(user: User, db: AsyncSession, employment_id: str) -> Employment:
    """Return the Employment if the user may access it, else raise."""
    employment = await db.get(Employment, employment_id)
    if not employment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employment not found")
    if is_super_admin(user):
        return employment
    if is_employee(user):
        employee = await db.get(Employee, employment.employee_id)
        if employee and employee.user_id == user.id:
            return employment
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employment not found")
    scope = await get_employer_scope(user, db)
    if employment.employer_id in scope:
        return employment
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employment not found")


async def assert_employee_access(user: User, db: AsyncSession, employee_id: str) -> Employee:
    """Return the Employee if the user may access it, else raise."""
    employee = await db.get(Employee, employee_id)
    if not employee:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    if is_super_admin(user):
        return employee
    if is_employee(user):
        if employee.user_id == user.id:
            return employee
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    scope = await get_employer_scope(user, db)
    if not scope:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    result = await db.execute(
        select(Employment.id).where(
            Employment.employee_id == employee_id,
            Employment.employer_id.in_(scope),
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return employee


async def assert_salary_profile_access(
    user: User, db: AsyncSession, salary_profile_id: str
) -> SalaryProfile:
    """Return the SalaryProfile if the user may access it, else raise."""
    profile = await db.get(SalaryProfile, salary_profile_id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Salary profile not found")
    if is_super_admin(user):
        return profile
    if is_employee(user):
        employment = await db.get(Employment, profile.employment_id)
        if employment:
            employee = await db.get(Employee, employment.employee_id)
            if employee and employee.user_id == user.id:
                return profile
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Salary profile not found")
    scope = await get_employer_scope(user, db)
    employment = await db.get(Employment, profile.employment_id)
    if employment and employment.employer_id in scope:
        return profile
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Salary profile not found")


async def get_current_user_role(user: User = Depends(get_current_user)) -> str:
    return _role(user)


def require_role(*allowed_roles: str):
    """Dependency factory: ensure the authenticated user has one of allowed roles."""

    async def _dependency(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        await require_roles(user, db, *allowed_roles)
        return user

    return _dependency


def require_employer_scope():
    """Dependency: returns (user, db, scope) for employer-scoped routes."""

    async def _dependency(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> tuple[User, AsyncSession, list[str]]:
        scope = await get_employer_scope(user, db)
        return user, db, scope

    return _dependency