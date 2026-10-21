from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Employment, SalaryProfile, User
from app.schemas.salary import SalaryProfileCreate, SalaryProfileRead, SalaryProfileUpdate
from app.services.salary_service import (
    create_salary_profile as create_salary_profile_service,
    get_active_salary_profile_by_employment,
    get_salary_profile_by_id,
)
from app.api.v1.auth import get_current_user
from app.core.authorization import (
    assert_salary_profile_access,
    is_super_admin,
    get_employer_scope,
    _user_has_scope,
)
from app.services.audit_service import (
    SALARY_PROFILE_CREATED,
    SALARY_PROFILE_UPDATED,
    record_audit_event,
)

router = APIRouter(prefix="/salary-profiles", tags=["salary"])


@router.post("/", response_model=SalaryProfileRead)
async def create_salary_profile(
    data: SalaryProfileCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not (is_super_admin(current_user) or await _user_has_scope(current_user, db)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    scope = await get_employer_scope(current_user, db)
    from app.models import Employment
    employment = await db.get(Employment, data.employment_id)
    if not employment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employment not found")
    if not is_super_admin(current_user) and employment.employer_id not in scope:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employment not found")
    try:
        profile = await create_salary_profile_service(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    await record_audit_event(
        db,
        actor_user_id=current_user.id,
        employer_id=employment.employer_id,
        action=SALARY_PROFILE_CREATED,
        entity_type="salary_profile",
        entity_id=profile.id,
        metadata={"employment_id": profile.employment_id, "monthly_salary_amount_minor": profile.monthly_salary_amount_minor},
    )
    await db.commit()
    await db.refresh(profile)
    return profile


@router.get("/{salary_profile_id}", response_model=SalaryProfileRead)
async def get_salary_profile(
    salary_profile_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await assert_salary_profile_access(current_user, db, salary_profile_id)


@router.put("/{salary_profile_id}", response_model=SalaryProfileRead)
async def update_salary_profile(
    salary_profile_id: str,
    data: SalaryProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await assert_salary_profile_access(current_user, db, salary_profile_id)
    from app.models import Employment
    employment = await db.get(Employment, profile.employment_id)
    before = {
        "monthly_salary_amount_minor": profile.monthly_salary_amount_minor,
        "currency": profile.currency,
        "pay_schedule": profile.pay_schedule,
        "status": profile.status,
    }
    for field in data.model_fields:
        value = getattr(data, field)
        if value is not None:
            setattr(profile, field, value)
    after = {
        "monthly_salary_amount_minor": profile.monthly_salary_amount_minor,
        "currency": profile.currency,
        "pay_schedule": profile.pay_schedule,
        "status": profile.status,
    }
    await record_audit_event(
        db,
        actor_user_id=current_user.id,
        employer_id=employment.employer_id if employment else None,
        action=SALARY_PROFILE_UPDATED,
        entity_type="salary_profile",
        entity_id=profile.id,
        metadata={"before": before, "after": after, "employment_id": profile.employment_id},
    )
    await db.commit()
    await db.refresh(profile)
    return profile


@router.get("/employment/{employment_id}", response_model=SalaryProfileRead)
async def get_active_salary_profile(
    employment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models import Employment
    employment = await db.get(Employment, employment_id)
    if not employment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employment not found")
    profile = await get_active_salary_profile_by_employment(db, employment_id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active salary profile not found")
    # Reuse the same authorization check on the resolved profile.
    await assert_salary_profile_access(current_user, db, profile.id)
    return profile