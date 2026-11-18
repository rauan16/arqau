from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Employer, EmployerAdmin, User, EwaPolicy
from app.schemas.employer import EmployerCreate, EmployerRead
from app.schemas.ewa import EwaPolicyCreate, EwaPolicyUpdate, EwaPolicyRead
from app.services.audit_service import EMPLOYER_CREATED, EWA_POLICY_CREATED, EWA_POLICY_UPDATED, record_audit_event
from app.services.employer_service import create_employer as create_employer_service
from app.api.v1.auth import get_current_user
from app.core.authorization import (
    assert_employer_access,
    is_super_admin,
    get_employer_scope,
)

router = APIRouter(prefix="/employers", tags=["employer"])


@router.post("/", response_model=EmployerRead)
async def create_employer(
    data: EmployerCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        employer = await create_employer_service(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    # Creator becomes an employer_admin for the new employer.
    db.add(EmployerAdmin(user_id=current_user.id, employer_id=employer.id))
    await record_audit_event(
        db,
        actor_user_id=current_user.id,
        employer_id=employer.id,
        action=EMPLOYER_CREATED,
        entity_type="employer",
        entity_id=employer.id,
        metadata={"legal_name": employer.legal_name},
    )
    await db.commit()
    await db.refresh(employer)
    return employer


@router.get("/{employer_id}", response_model=EmployerRead)
async def get_employer(
    employer_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await assert_employer_access(current_user, db, employer_id)


@router.get("/{employer_id}/ewa/policy", response_model=EwaPolicyRead)
async def get_ewa_policy(
    employer_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await assert_employer_access(current_user, db, employer_id)
    result = await db.execute(select(EwaPolicy).where(EwaPolicy.employer_id == employer_id))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="EWA policy not found")
    return policy


@router.put("/{employer_id}/ewa/policy", response_model=EwaPolicyRead)
async def upsert_ewa_policy(
    employer_id: str,
    data: EwaPolicyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    employer = await assert_employer_access(current_user, db, employer_id)

    # Only employer_admin and super_admin can mutate; finance_manager is read-only
    from app.core.authorization import is_employer_admin, is_finance_manager
    if is_finance_manager(current_user) and not is_super_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Finance manager cannot mutate EWA policy")

    result = await db.execute(select(EwaPolicy).where(EwaPolicy.employer_id == employer_id))
    policy = result.scalar_one_or_none()

    if policy:
        # Update
        before = {
            "enabled": policy.enabled,
            "max_access_percentage": policy.max_access_percentage,
            "max_withdrawals_per_period": policy.max_withdrawals_per_period,
            "minimum_tenure_days": policy.minimum_tenure_days,
            "minimum_remaining_salary_minor": policy.minimum_remaining_salary_minor,
            "minimum_withdrawal_minor": policy.minimum_withdrawal_minor,
            "maximum_withdrawal_minor": policy.maximum_withdrawal_minor,
        }
        policy.enabled = data.enabled
        policy.max_access_percentage = data.max_access_percentage
        policy.max_withdrawals_per_period = data.max_withdrawals_per_period
        policy.minimum_tenure_days = data.minimum_tenure_days
        policy.minimum_remaining_salary_minor = data.minimum_remaining_salary_minor
        policy.minimum_withdrawal_minor = data.minimum_withdrawal_minor
        policy.maximum_withdrawal_minor = data.maximum_withdrawal_minor
        await record_audit_event(
            db,
            actor_user_id=current_user.id,
            employer_id=employer_id,
            action=EWA_POLICY_UPDATED,
            entity_type="ewa_policy",
            entity_id=policy.id,
            before_data=before,
            after_data=data.model_dump(),
        )
    else:
        # Create
        policy = EwaPolicy(
            employer_id=employer_id,
            enabled=data.enabled,
            max_access_percentage=data.max_access_percentage,
            max_withdrawals_per_period=data.max_withdrawals_per_period,
            minimum_tenure_days=data.minimum_tenure_days,
            minimum_remaining_salary_minor=data.minimum_remaining_salary_minor,
            minimum_withdrawal_minor=data.minimum_withdrawal_minor,
            maximum_withdrawal_minor=data.maximum_withdrawal_minor,
        )
        db.add(policy)
        await db.flush()
        await record_audit_event(
            db,
            actor_user_id=current_user.id,
            employer_id=employer_id,
            action=EWA_POLICY_CREATED,
            entity_type="ewa_policy",
            entity_id=policy.id,
            after_data=data.model_dump(),
        )

    await db.commit()
    await db.refresh(policy)
    return policy