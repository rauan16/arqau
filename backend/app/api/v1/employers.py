from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Employer, EmployerAdmin, User
from app.schemas.employer import EmployerCreate, EmployerRead
from app.services.audit_service import EMPLOYER_CREATED, record_audit_event
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