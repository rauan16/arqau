from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SalaryProfile
from app.schemas.salary import SalaryProfileCreate, SalaryProfileRead


async def create_salary_profile(db: AsyncSession, data: SalaryProfileCreate) -> SalaryProfile:
    existing = (
        await db.execute(select(SalaryProfile).where(SalaryProfile.employment_id == data.employment_id))
    ).scalar_one_or_none()
    if existing:
        raise ValueError("A salary profile already exists for this employment")
    profile = SalaryProfile(
        employment_id=data.employment_id,
        currency=data.currency,
        monthly_salary_amount_minor=data.monthly_salary_amount_minor,
        pay_schedule=data.pay_schedule,
        payday_day=data.payday_day,
        effective_from=data.effective_from,
        effective_to=data.effective_to,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


async def get_salary_profile_by_id(db: AsyncSession, salary_profile_id: str) -> SalaryProfile | None:
    result = await db.execute(select(SalaryProfile).where(SalaryProfile.id == salary_profile_id))
    return result.scalar_one_or_none()


async def get_active_salary_profile_by_employment(
    db: AsyncSession, employment_id: str
) -> SalaryProfile | None:
    result = await db.execute(
        select(SalaryProfile)
        .where(
            SalaryProfile.employment_id == employment_id,
            SalaryProfile.status == "active",
        )
    )
    return result.scalar_one_or_none()
