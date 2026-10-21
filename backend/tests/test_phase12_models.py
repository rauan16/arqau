from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.core.database import Base, configure_database, create_database
from app.models import (
    Employee,
    Employer,
    Employment,
    SalaryProfile,
    User,
)
from app.schemas.employee import EmployeeCreate
from app.schemas.employment import EmploymentCreate
from app.schemas.salary import SalaryProfileCreate
from app.services.employee_service import create_employee
from app.services.salary_service import get_active_salary_profile_by_employment


class Phase12ModelTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "models.db"
        self.database_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
        self.original_url = Settings(environment="testing").database_url
        self.engine, self.sessions = create_database(self.database_url)
        await configure_database(self.database_url)
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self) -> None:
        await configure_database(self.original_url)
        await self.engine.dispose()
        self.temp_dir.cleanup()

    async def test_employer_can_be_created(self) -> None:
        employer = Employer(legal_name="Acme Corp")
        async with self.sessions() as session:
            session.add(employer)
            await session.commit()
        self.assertEqual(employer.legal_name, "Acme Corp")
        self.assertEqual(employer.status, "active")

    async def test_employee_can_link_to_existing_user(self) -> None:
        async with self.sessions() as session:
            user = User(id="user-1", email="employee@example.test", hashed_password="hashed")
            employee = Employee(user_id=user.id, external_employee_id="EMP-1")
            session.add_all([user, employee])
            await session.commit()

            result = await session.execute(
                select(Employee)
                .where(Employee.id == employee.id)
                .options(selectinload(Employee.user))
            )
            loaded = result.scalar_one()
            self.assertEqual(loaded.user_id, user.id)
            self.assertEqual(loaded.user.id, user.id)

    async def test_duplicate_employee_for_same_user_is_rejected(self) -> None:
        async with self.sessions() as session:
            user = User(id="user-2", email="duplicate@example.test", hashed_password="hashed")
            employee = Employee(user_id=user.id)
            session.add_all([user, employee])
            await session.commit()
            with self.assertRaises(ValueError):
                await create_employee(session, EmployeeCreate(user_id=user.id))

    async def test_employment_links_employee_to_employer(self) -> None:
        async with self.sessions() as session:
            user = User(id="user-3", email="employment@example.test", hashed_password="hashed")
            employee = Employee(user_id=user.id)
            employer = Employer(legal_name="Acme Corp")
            session.add_all([user, employee, employer])
            await session.flush()

            employment = Employment(
                employee_id=employee.id,
                employer_id=employer.id,
                status="active",
            )
            session.add(employment)
            await session.commit()

            result = await session.execute(
                select(Employment)
                .where(Employment.id == employment.id)
                .options(
                    selectinload(Employment.employee).selectinload(Employee.employments),
                    selectinload(Employment.employer).selectinload(Employer.employments),
                )
            )
            loaded = result.scalar_one()
            self.assertEqual(loaded.employee.id, employee.id)
            self.assertEqual(loaded.employer.id, employer.id)
            self.assertEqual(loaded.employee.employments[0].id, employment.id)
            self.assertEqual(loaded.employer.employments[0].id, employment.id)

    async def test_salary_profile_links_to_employment(self) -> None:
        async with self.sessions() as session:
            user = User(id="user-4", email="salary@example.test", hashed_password="hashed")
            employee = Employee(user_id=user.id)
            employer = Employer(legal_name="Acme Corp")
            session.add_all([user, employee, employer])
            await session.flush()

            employment = Employment(
                employee_id=employee.id,
                employer_id=employer.id,
                status="active",
            )
            session.add(employment)
            await session.flush()

            profile = SalaryProfile(
                employment_id=employment.id,
                currency="USD",
                monthly_salary_amount_minor=100000,
                effective_from=datetime(2026, 1, 1),
            )
            session.add(profile)
            await session.commit()

            result = await session.execute(
                select(SalaryProfile)
                .where(SalaryProfile.id == profile.id)
                .options(selectinload(SalaryProfile.employment))
            )
            loaded = result.scalar_one()
            self.assertEqual(loaded.employment_id, employment.id)
            self.assertEqual(loaded.employment.id, employment.id)

    def test_monthly_salary_amount_minor_must_be_positive(self) -> None:
        with self.assertRaises(ValidationError):
            SalaryProfileCreate(
                employment_id="emp",
                currency="USD",
                monthly_salary_amount_minor=0,
                effective_from="2026-01-01T00:00:00",
            )
        with self.assertRaises(ValidationError):
            SalaryProfileCreate(
                employment_id="emp",
                currency="USD",
                monthly_salary_amount_minor=-100,
                effective_from="2026-01-01T00:00:00",
            )

    def test_invalid_employment_dates_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            EmploymentCreate(
                employee_id="emp",
                employer_id="emp",
                start_date="2026-02-01T00:00:00",
                end_date="2026-01-01T00:00:00",
            )

    def test_invalid_salary_effective_dates_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            SalaryProfileCreate(
                employment_id="emp",
                currency="USD",
                monthly_salary_amount_minor=1,
                effective_from="2026-02-01T00:00:00",
                effective_to="2026-01-01T00:00:00",
            )

    async def test_inactive_historical_employment_is_representable(self) -> None:
        async with self.sessions() as session:
            user = User(id="user-5", email="inactive@example.test", hashed_password="hashed")
            employer = Employer(legal_name="Acme Corp")
            employee = Employee(user_id=user.id)
            session.add_all([user, employer, employee])
            await session.flush()

            employment = Employment(
                employee_id=employee.id,
                employer_id=employer.id,
                status="terminated",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2025, 12, 31),
            )
            session.add(employment)
            await session.commit()

            result = await session.execute(
                select(Employment).where(Employment.id == employment.id)
            )
            loaded = result.scalar_one()
            self.assertEqual(loaded.status, "terminated")
            self.assertEqual(loaded.end_date, employment.end_date)

    async def test_active_salary_profile_retrieval_works(self) -> None:
        async with self.sessions() as session:
            user = User(id="user-6", email="salary-active@example.test", hashed_password="hashed")
            employer = Employer(legal_name="Acme Corp")
            employee = Employee(user_id=user.id)
            session.add_all([user, employer, employee])
            await session.flush()

            employment = Employment(
                employee_id=employee.id,
                employer_id=employer.id,
                status="active",
            )
            session.add(employment)
            await session.flush()

            active = SalaryProfile(
                employment_id=employment.id,
                currency="USD",
                monthly_salary_amount_minor=100,
                effective_from=datetime(2026, 1, 1),
                status="active",
            )
            session.add(active)
            await session.commit()

            result = await get_active_salary_profile_by_employment(session, employment.id)
            self.assertEqual(result.id, active.id)


if __name__ == "__main__":
    unittest.main()
