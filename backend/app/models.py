from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, Index, String, Text, text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from uuid import uuid4
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    is_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    onboarding = relationship("Onboarding", back_populates="user", uselist=False)
    transactions = relationship("Transaction", back_populates="user")
    budgets = relationship("Budget", back_populates="user")
    goals = relationship("Goal", back_populates="user")
    earned_wages = relationship("EarnedWages", back_populates="user", uselist=False)
    wage_requests = relationship("WageAccessRequest", back_populates="user")
    employee = relationship("Employee", back_populates="user")


class Onboarding(Base):
    __tablename__ = "onboarding"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), unique=True, nullable=False)
    pay_frequency = Column(String, nullable=True)
    monthly_income_range = Column(String, nullable=True)
    payday_range = Column(String, nullable=True)
    financial_pressure = Column(String, nullable=True)
    early_access_use_case = Column(String, nullable=True)
    ai_help_preference = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="onboarding")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    type = Column(String, nullable=False)
    amount_minor = Column(Integer, nullable=False)
    category = Column(String, nullable=True)
    merchant = Column(String, nullable=True)
    description = Column(String, nullable=True)
    date = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="transactions")


class Budget(Base):
    __tablename__ = "budgets"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    category = Column(String, nullable=False)
    limit_minor = Column(Integer, nullable=False)
    spent_minor = Column(Integer, default=0)
    period = Column(String, default="monthly")
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="budgets")


class Goal(Base):
    __tablename__ = "goals"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    target_minor = Column(Integer, nullable=False)
    current_minor = Column(Integer, default=0)
    deadline = Column(String, nullable=True)
    status = Column(String, default="active")
    progress_pct = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="goals")


class EarnedWages(Base):
    __tablename__ = "earned_wages"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), unique=True, nullable=False)
    earned_amount_minor = Column(Integer, default=0)
    accessed_amount_minor = Column(Integer, default=0)
    available_amount_minor = Column(Integer, default=0)
    period_start = Column(String, nullable=True)
    period_end = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="earned_wages")


class WageAccessRequest(Base):
    __tablename__ = "wage_access_requests"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    amount_minor = Column(Integer, nullable=False)
    status = Column(String, default="pending")
    reason = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="wage_requests")


class Employer(Base):
    __tablename__ = "employers"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    legal_name = Column(String, nullable=False)
    display_name = Column(String, nullable=True)
    registration_number = Column(String, nullable=True)
    country = Column(String, nullable=True)
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_employers_status", "status"),
    )

    employments = relationship("Employment", back_populates="employer")


class Employee(Base):
    __tablename__ = "employees"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    external_employee_id = Column(String, nullable=True)
    display_name = Column(String, nullable=True)
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_employees_user_id", "user_id", unique=True),
        Index("ix_employees_status", "status"),
    )

    user = relationship("User", back_populates="employee")
    employments = relationship("Employment", back_populates="employee")


class Employment(Base):
    __tablename__ = "employments"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    employee_id = Column(String, ForeignKey("employees.id"), nullable=False)
    employer_id = Column(String, ForeignKey("employers.id"), nullable=False)
    employment_type = Column(String, nullable=True)
    status = Column(String, default="active")
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    eligible_from = Column(DateTime, nullable=True)
    eligible_to = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_employments_employee_id", "employee_id"),
        Index("ix_employments_employer_id", "employer_id"),
        Index("ix_employments_status", "status"),
        CheckConstraint(
            text("(end_date IS NULL OR end_date >= start_date) AND (eligible_to IS NULL OR eligible_to >= eligible_from)"),
            name="ck_employments_dates",
        ),
    )

    employee = relationship("Employee", back_populates="employments")
    employer = relationship("Employer", back_populates="employments")
    salary_profile = relationship("SalaryProfile", back_populates="employment", uselist=False)


class SalaryProfile(Base):
    __tablename__ = "salary_profiles"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    employment_id = Column(String, ForeignKey("employments.id"), nullable=False)
    currency = Column(String, default="USD")
    monthly_salary_amount_minor = Column(Integer, nullable=False)
    pay_schedule = Column(String, default="monthly")
    payday_day = Column(Integer, nullable=True)
    effective_from = Column(DateTime, nullable=False)
    effective_to = Column(DateTime, nullable=True)
    status = Column(String, default="active")
    source = Column(String, default="manual")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_salary_profiles_employment_id", "employment_id", unique=True),
        Index("ix_salary_profiles_status", "status"),
        CheckConstraint(
            text("(effective_to IS NULL OR effective_to >= effective_from)"),
            name="ck_salary_profiles_effective_dates",
        ),
    )

    employment = relationship("Employment", back_populates="salary_profile")
