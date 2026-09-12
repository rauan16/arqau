from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import SalaryProfile, User
from app.schemas.salary import SalaryProfileCreate, SalaryProfileRead, SalaryProfileUpdate
from app.services.salary_service import (
    create_salary_profile as create_salary_profile_service,
    get_active_salary_profile_by_employment,
    get_salary_profile_by_id,
)
from app.api.v1.auth import get_current_user

router = APIRouter(prefix="/salary-profiles", tags=["salary"])


@router.post("/", response_model=SalaryProfileRead)
async def create_salary_profile(
    data: SalaryProfileCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        profile = await create_salary_profile_service(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return profile


@router.get("/{salary_profile_id}", response_model=SalaryProfileRead)
async def get_salary_profile(
    salary_profile_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await get_salary_profile_by_id(db, salary_profile_id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Salary profile not found")
    return profile


@router.put("/{salary_profile_id}", response_model=SalaryProfileRead)
async def update_salary_profile(
    salary_profile_id: str,
    data: SalaryProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await get_salary_profile_by_id(db, salary_profile_id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Salary profile not found")
    for field in data.model_fields:
        value = getattr(data, field)
        if value is not None:
            setattr(profile, field, value)
    await db.commit()
    await db.refresh(profile)
    return profile


@router.get("/employment/{employment_id}", response_model=SalaryProfileRead)
async def get_active_salary_profile(
    employment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await get_active_salary_profile_by_employment(db, employment_id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active salary profile not found")
    return profile
