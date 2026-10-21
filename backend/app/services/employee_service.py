from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Employee, User
from app.schemas.employee import EmployeeCreate, EmployeeRead


async def create_employee(db: AsyncSession, data: EmployeeCreate) -> Employee:
    user = (await db.execute(select(User).where(User.id == data.user_id))).scalar_one_or_none()
    if not user:
        raise ValueError("User not found")

    existing = (
        await db.execute(select(Employee).where(Employee.user_id == data.user_id))
    ).scalar_one_or_none()
    if existing:
        raise ValueError("An employee profile already exists for this user")

    employee = Employee(
        user_id=data.user_id,
        external_employee_id=data.external_employee_id,
        display_name=data.display_name,
        status=data.status,
    )
    db.add(employee)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise ValueError("An employee profile already exists for this user")
    await db.refresh(employee)
    return employee


async def get_employee_by_id(db: AsyncSession, employee_id: str) -> Employee | None:
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    return result.scalar_one_or_none()


async def get_employee_by_user_id(db: AsyncSession, user_id: str) -> Employee | None:
    result = await db.execute(select(Employee).where(Employee.user_id == user_id))
    return result.scalar_one_or_none()
