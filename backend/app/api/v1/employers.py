from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Employer, User
from app.schemas.employer import EmployerCreate, EmployerRead
from app.services.employer_service import create_employer as create_employer_service, get_employer_by_id
from app.api.v1.auth import get_current_user

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
    return employer


@router.get("/{employer_id}", response_model=EmployerRead)
async def get_employer(
    employer_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    employer = await get_employer_by_id(db, employer_id)
    if not employer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employer not found")
    return employer
