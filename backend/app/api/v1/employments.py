from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Employment, User
from app.schemas.employment import EmploymentCreate, EmploymentRead
from app.services.audit_service import EMPLOYMENT_CREATED, record_audit_event
from app.services.employment_service import create_employment as create_employment_service
from app.api.v1.auth import get_current_user
from app.core.authorization import (
    assert_employment_access,
    is_super_admin,
    get_employer_scope,
    _user_has_scope,
)

router = APIRouter(prefix="/employments", tags=["employment"])


@router.post("/", response_model=EmploymentRead)
async def create_employment(
    data: EmploymentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Only scoped employer admins or super admins may create employments.
    if not (is_super_admin(current_user) or await _user_has_scope(current_user, db)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    scope = await get_employer_scope(current_user, db)
    if not is_super_admin(current_user) and data.employer_id not in scope:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employer not found")
    try:
        employment = await create_employment_service(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    await record_audit_event(
        db,
        actor_user_id=current_user.id,
        employer_id=employment.employer_id,
        action=EMPLOYMENT_CREATED,
        entity_type="employment",
        entity_id=employment.id,
        metadata={"employee_id": employment.employee_id},
    )
    await db.commit()
    await db.refresh(employment)
    return employment


@router.get("/{employment_id}", response_model=EmploymentRead)
async def get_employment(
    employment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await assert_employment_access(current_user, db, employment_id)