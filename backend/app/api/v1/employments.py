from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Employer, Employment, User
from app.schemas.employment import EmploymentCreate, EmploymentRead
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
        return await create_employment_service(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("/{employment_id}", response_model=EmploymentRead)
async def get_employment(
    employment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await assert_employment_access(current_user, db, employment_id)