from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Employer
from app.schemas.employer import EmployerCreate, EmployerRead


async def create_employer(db: AsyncSession, data: EmployerCreate) -> Employer:
    employer = Employer(
        legal_name=data.legal_name,
        display_name=data.display_name,
        registration_number=data.registration_number,
        country=data.country,
    )
    db.add(employer)
    await db.commit()
    await db.refresh(employer)
    return employer


async def get_employer_by_id(db: AsyncSession, employer_id: str) -> Employer | None:
    result = await db.execute(select(Employer).where(Employer.id == employer_id))
    return result.scalar_one_or_none()
