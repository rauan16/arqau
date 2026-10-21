from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Employee, Employer, Employment
from app.schemas.employment import EmploymentCreate, EmploymentRead


async def create_employment(db: AsyncSession, data: EmploymentCreate) -> Employment:
    employer = (
        await db.execute(select(Employer).where(Employer.id == data.employer_id))
    ).scalar_one_or_none()
    if not employer:
        raise ValueError("Employer not found")

    employee = (
        await db.execute(select(Employee).where(Employee.id == data.employee_id))
    ).scalar_one_or_none()
    if not employee:
        raise ValueError("Employee not found")

    employment = Employment(
        employee_id=data.employee_id,
        employer_id=data.employer_id,
        employment_type=data.employment_type,
        status=data.status,
        start_date=data.start_date,
        end_date=data.end_date,
        eligible_from=data.eligible_from,
        eligible_to=data.eligible_to,
    )
    db.add(employment)
    await db.commit()
    await db.refresh(employment)
    return employment


async def get_employment_by_id(db: AsyncSession, employment_id: str) -> Employment | None:
    result = await db.execute(select(Employment).where(Employment.id == employment_id))
    return result.scalar_one_or_none()
