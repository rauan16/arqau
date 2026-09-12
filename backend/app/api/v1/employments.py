from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Employer, Employment, User
from app.schemas.employment import EmploymentCreate, EmploymentRead
from app.services.employment_service import create_employment as create_employment_service, get_employment_by_id
from app.api.v1.auth import get_current_user

router = APIRouter(prefix="/employments", tags=["employment"])


@router.post("/", response_model=EmploymentRead)
async def create_employment(
    data: EmploymentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        employment = await create_employment_service(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return employment


@router.get("/{employment_id}", response_model=EmploymentRead)
async def get_employment(
    employment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    employment = await get_employment_by_id(db, employment_id)
    if not employment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employment not found")
    return employment
