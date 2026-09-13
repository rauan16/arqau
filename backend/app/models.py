from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, Index, JSON, String, Text, UniqueConstraint, text
from sqlalchemy.orm import relationship, Mapped
from datetime import datetime
from uuid import uuid4
from app.database import Base

# Role constants. Stored as plain strings on User.role.
ROLE_EMPLOYEE = "employee"
ROLE_EMPLOYER_ADMIN = "employer_admin"
ROLE_FINANCE_MANAGER = "finance_manager"
ROLE_SUPER_ADMIN = "super_admin"

# Default role assigned to legacy users who have no explicit role.
DEFAULT_ROLE = ROLE_EMPLOYEE

VALID_ROLES = (ROLE_EMPLOYEE, ROLE_EMPLOYER_ADMIN, ROLE_FINANCE_MANAGER, ROLE_SUPER_ADMIN)


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    is_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    # Explicit role. Legacy users without a value default to employee.
    role = Column(String, nullable=False, server_default=DEFAULT_ROLE)
    created_at = Column(DateTime, default=datetime.utcnow)

    onboarding = relationship("Onboarding", back_populates="user", uselist=False)
    transactions = relationship("Transaction", back_populates="user")
    budgets = relationship("Budget", back_populates="user")
    goals = relationship("Goal", back_populates="user")
    earned_wages = relationship("EarnedWages", back_populates="user", uselist=False)
    wage_requests = relationship("WageAccessRequest", back_populates="user")
    employee = relationship("Employee", back_populates="user")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    employer_admins = relationship("EmployerAdmin", back_populates="user", cascade="all, delete-orphan")


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
    employer_admins = relationship("EmployerAdmin", back_populates="employer")


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


class RefreshToken(Base):
    """Persistent refresh token.

    Only a SHA-256 hash of the token is stored. The plaintext token is
    never persisted. Rotation replaces the token: a new row is created
    and the previous row is marked revoked via rotated_from_id + revoked_at.
    """

    __tablename__ = "refresh_tokens"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String, nullable=False, unique=True)
    family_id = Column(String, nullable=False)
    rotated_from_id = Column(String, ForeignKey("refresh_tokens.id", ondelete="SET NULL"), nullable=True)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
        Index("ix_refresh_tokens_family_id", "family_id"),
        Index("ix_refresh_tokens_user_id", "user_id"),
        Index("ix_refresh_tokens_revoked_at", "revoked_at"),
    )

    user = relationship("User", back_populates="refresh_tokens")
    rotated_from = relationship("RefreshToken", remote_side=[id], viewonly=True)


class EmployerAdmin(Base):
    """Explicit employer-admin membership.

    A user with role employer_admin is scoped to the employers listed here.
    super_admin has no rows here and is unrestricted.
    """

    __tablename__ = "employer_admins"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    employer_id = Column(String, ForeignKey("employers.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "employer_id", name="uq_employer_admins_user_employer"),
    )

    user = relationship("User", back_populates="employer_admins")
    employer = relationship("Employer", back_populates="employer_admins")


class AuditLog(Base):
    """Immutable audit trail for security and business actions.

    actor_user_id and employer_id are nullable: some events (e.g. failed
    login attempts) may not have a resolved actor or employer scope.
    """

    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    actor_user_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    employer_id = Column(String, ForeignKey("employers.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String, nullable=False, index=True)
    entity_type = Column(String, nullable=True, index=True)
    entity_id = Column(String, nullable=True, index=True)
    request_id = Column(String, nullable=True, index=True)
    details = Column("metadata", JSON, nullable=True)
    before_data = Column(JSON, nullable=True)
    after_data = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"), index=True)

    __table_args__ = (
        Index("ix_audit_logs_action_created", "action", "created_at"),
        Index("ix_audit_logs_employer_created", "employer_id", "created_at"),
        Index("ix_audit_logs_actor_created", "actor_user_id", "created_at"),
    )

    actor = relationship("User", viewonly=True)
    employer = relationship("Employer", viewonly=True)
