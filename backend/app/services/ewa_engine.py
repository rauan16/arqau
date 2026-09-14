"""Deterministic EWA Calculation Engine.

This module provides the authoritative backend calculation for earned wage access.
No AI, no demo income ranges, no floating-point money.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    EwaPolicy,
    Employee,
    Employment,
    SalaryProfile,
    WageAccessRequest,
)


# --- Eligibility reason codes ---
class EligibilityReason:
    NO_EMPLOYMENT = "NO_EMPLOYMENT"
    EMPLOYMENT_INACTIVE = "EMPLOYMENT_INACTIVE"
    EMPLOYMENT_NOT_STARTED = "EMPLOYMENT_NOT_STARTED"
    EMPLOYMENT_ENDED = "EMPLOYMENT_ENDED"
    NOT_YET_EWA_ELIGIBLE = "NOT_YET_EWA_ELIGIBLE"
    EWA_ELIGIBILITY_ENDED = "EWA_ELIGIBILITY_ENDED"
    NO_ACTIVE_SALARY_PROFILE = "NO_ACTIVE_SALARY_PROFILE"
    SALARY_NOT_EFFECTIVE = "SALARY_NOT_EFFECTIVE"
    INVALID_SALARY = "INVALID_SALARY"
    NO_EWA_POLICY = "NO_EWA_POLICY"
    EWA_DISABLED = "EWA_DISABLED"
    MINIMUM_TENURE_NOT_MET = "MINIMUM_TENURE_NOT_MET"


@dataclass(frozen=True)
class EWAResult:
    """Authoritative EWA calculation result. All monetary values in minor units."""
    salary_amount_minor: int
    earned_amount_minor: int
    policy_limit_minor: int
    reserved_amount_minor: int
    paid_amount_minor: int
    available_amount_minor: int
    pay_period_start: date
    pay_period_end: date
    calculation_date: date
    eligible: bool
    eligibility_reasons: tuple[str, ...]
    minimum_withdrawal_minor: Optional[int] = None
    maximum_withdrawal_minor: Optional[int] = None
    can_request_withdrawal: bool = False


def _get_pay_period(calculation_date: date) -> tuple[date, date]:
    """Get the calendar month pay period for the given calculation date.

    Rule: Monthly salary accrual period = calendar month containing calculation_date.
    This is independent of payday_day which describes payment timing, not accrual.

    Args:
        calculation_date: The date for which to calculate the pay period.

    Returns:
        Tuple of (period_start, period_end) as dates.
    """
    period_start = date(calculation_date.year, calculation_date.month, 1)
    # Last day of month
    if calculation_date.month == 12:
        period_end = date(calculation_date.year + 1, 1, 1)
    else:
        period_end = date(calculation_date.year, calculation_date.month + 1, 1)
    from datetime import timedelta
    period_end = period_end - timedelta(days=1)
    return period_start, period_end


def _count_working_days(start: date, end: date) -> int:
    """Count Monday-Friday days inclusive between start and end.

    Args:
        start: Inclusive start date.
        end: Inclusive end date.

    Returns:
        Number of working days (Mon-Fri).
    """
    if start > end:
        return 0
    count = 0
    current = start
    while current <= end:
        if current.weekday() < 5:  # Mon=0, Fri=4
            count += 1
        from datetime import timedelta
        current += timedelta(days=1)
    return count


async def _get_active_employment(db: AsyncSession, employee_id: str, calculation_date: date) -> Employment | None:
    """Get the active employment for an employee at the calculation date."""
    result = await db.execute(
        select(Employment)
        .where(
            Employment.employee_id == employee_id,
            Employment.status == "active",
        )
    )
    employments = result.scalars().all()

    for emp in employments:
        # Check employment status and date bounds
        if emp.start_date and emp.start_date.date() > calculation_date:
            continue  # Not started yet
        if emp.end_date and emp.end_date.date() <= calculation_date:
            continue  # Already ended (end_date is exclusive boundary per check constraint)
        if emp.eligible_from and emp.eligible_from.date() > calculation_date:
            continue  # Not yet eligible
        if emp.eligible_to and emp.eligible_to.date() <= calculation_date:
            continue  # Eligibility ended
        return emp
    return None


async def _get_active_salary_profile(db: AsyncSession, employment_id: str, calculation_date: date) -> SalaryProfile | None:
    """Get the active salary profile for an employment at the calculation date."""
    result = await db.execute(
        select(SalaryProfile)
        .where(
            SalaryProfile.employment_id == employment_id,
            SalaryProfile.status == "active",
            SalaryProfile.effective_from <= calculation_date,
        )
    )
    profiles = result.scalars().all()

    for profile in profiles:
        if profile.effective_to and profile.effective_to.date() <= calculation_date:
            continue  # Expired
        return profile
    return None


async def _get_ewa_policy(db: AsyncSession, employer_id: str) -> EwaPolicy | None:
    """Get the EWA policy for an employer."""
    result = await db.execute(
        select(EwaPolicy).where(EwaPolicy.employer_id == employer_id)
    )
    return result.scalar_one_or_none()


async def _get_existing_requests_summary(
    db: AsyncSession, user_id: str, pay_period_start: date, pay_period_end: date
) -> tuple[int, int]:
    """Get reserved and paid amounts from existing wage access requests.

    Returns:
        Tuple of (reserved_amount_minor, paid_amount_minor)

    Note: Phase 2.3 uses legacy status semantics. reserved = pending/approved, paid = paid.
    """
    result = await db.execute(
        select(WageAccessRequest)
        .where(
            WageAccessRequest.user_id == user_id,
            WageAccessRequest.created_at >= pay_period_start,
            WageAccessRequest.created_at <= pay_period_end,
        )
    )
    requests = result.scalars().all()

    reserved = 0
    paid = 0
    for req in requests:
        if req.status in ("pending", "approved"):
            reserved += req.amount_minor
        elif req.status == "paid":
            paid += req.amount_minor
    return reserved, paid


def _calculate_earned(
    monthly_salary_minor: int,
    pay_period_start: date,
    pay_period_end: date,
    effective_start: date,
    effective_end: date,
    calculation_date: date,
) -> int:
    """Calculate earned amount using integer arithmetic.

    Formula: monthly_salary * elapsed_working_days // total_working_days

    Args:
        monthly_salary_minor: Full monthly salary in minor units.
        pay_period_start: Start of pay period (calendar month start).
        pay_period_end: End of pay period (calendar month end).
        effective_start: Effective start of eligibility (max of employment/salary/period starts).
        effective_end: Effective end of eligibility (min of employment/salary/period ends).
        calculation_date: Date of calculation (today).

    Returns:
        Earned amount in minor units (floor rounded).
    """
    # The accrual window is bounded by both the pay period and eligibility dates
    accrual_start = max(pay_period_start, effective_start)
    accrual_end = min(pay_period_end, effective_end, calculation_date)

    if accrual_start > accrual_end:
        return 0

    total_working_days = _count_working_days(pay_period_start, pay_period_end)
    elapsed_working_days = _count_working_days(accrual_start, accrual_end)

    if total_working_days == 0:
        return 0

    # Integer floor division
    return (monthly_salary_minor * elapsed_working_days) // total_working_days


async def calculate_ewa(
    db: AsyncSession,
    user_id: str,
    calculation_date: Optional[date] = None,
) -> EWAResult:
    """Calculate authoritative EWA result for an authenticated employee.

    This is the single source of truth for EWA calculations.
    No AI, no demo data, integer money only.

    Args:
        db: Database session.
        user_id: Authenticated user ID.
        calculation_date: Date for calculation (defaults to today UTC).

    Returns:
        EWAResult with all calculated fields and eligibility status.
    """
    if calculation_date is None:
        calculation_date = datetime.utcnow().date()

    # 1. Get employee record
    result = await db.execute(select(Employee).where(Employee.user_id == user_id))
    employee = result.scalar_one_or_none()
    if not employee:
        return EWAResult(
            salary_amount_minor=0,
            earned_amount_minor=0,
            policy_limit_minor=0,
            reserved_amount_minor=0,
            paid_amount_minor=0,
            available_amount_minor=0,
            pay_period_start=calculation_date,
            pay_period_end=calculation_date,
            calculation_date=calculation_date,
            eligible=False,
            eligibility_reasons=(EligibilityReason.NO_EMPLOYMENT,),
        )

    # 2. Get active employment
    employment = await _get_active_employment(db, employee.id, calculation_date)
    if not employment:
        # Determine specific reason
        result = await db.execute(
            select(Employment).where(Employment.employee_id == employee.id)
        )
        employments = result.scalars().all()

        if not employments:
            reasons = (EligibilityReason.NO_EMPLOYMENT,)
        else:
            reasons = []
            for emp in employments:
                if emp.status != "active":
                    reasons.append(EligibilityReason.EMPLOYMENT_INACTIVE)
                elif emp.start_date and emp.start_date.date() > calculation_date:
                    reasons.append(EligibilityReason.EMPLOYMENT_NOT_STARTED)
                elif emp.end_date and emp.end_date.date() <= calculation_date:
                    reasons.append(EligibilityReason.EMPLOYMENT_ENDED)
                elif emp.eligible_from and emp.eligible_from.date() > calculation_date:
                    reasons.append(EligibilityReason.NOT_YET_EWA_ELIGIBLE)
                elif emp.eligible_to and emp.eligible_to.date() <= calculation_date:
                    reasons.append(EligibilityReason.EWA_ELIGIBILITY_ENDED)

            if not reasons:
                reasons = [EligibilityReason.NO_EMPLOYMENT]

        return EWAResult(
            salary_amount_minor=0,
            earned_amount_minor=0,
            policy_limit_minor=0,
            reserved_amount_minor=0,
            paid_amount_minor=0,
            available_amount_minor=0,
            pay_period_start=calculation_date,
            pay_period_end=calculation_date,
            calculation_date=calculation_date,
            eligible=False,
            eligibility_reasons=tuple(set(reasons)),
        )

    # 3. Get active salary profile
    salary_profile = await _get_active_salary_profile(db, employment.id, calculation_date)
    if not salary_profile:
        return EWAResult(
            salary_amount_minor=0,
            earned_amount_minor=0,
            policy_limit_minor=0,
            reserved_amount_minor=0,
            paid_amount_minor=0,
            available_amount_minor=0,
            pay_period_start=calculation_date,
            pay_period_end=calculation_date,
            calculation_date=calculation_date,
            eligible=False,
            eligibility_reasons=(EligibilityReason.NO_ACTIVE_SALARY_PROFILE,),
        )

    # Validate salary
    if salary_profile.monthly_salary_amount_minor <= 0:
        return EWAResult(
            salary_amount_minor=salary_profile.monthly_salary_amount_minor,
            earned_amount_minor=0,
            policy_limit_minor=0,
            reserved_amount_minor=0,
            paid_amount_minor=0,
            available_amount_minor=0,
            pay_period_start=calculation_date,
            pay_period_end=calculation_date,
            calculation_date=calculation_date,
            eligible=False,
            eligibility_reasons=(EligibilityReason.INVALID_SALARY,),
        )

    # 4. Get EWA policy
    policy = await _get_ewa_policy(db, employment.employer_id)
    if not policy:
        return EWAResult(
            salary_amount_minor=salary_profile.monthly_salary_amount_minor,
            earned_amount_minor=0,
            policy_limit_minor=0,
            reserved_amount_minor=0,
            paid_amount_minor=0,
            available_amount_minor=0,
            pay_period_start=calculation_date,
            pay_period_end=calculation_date,
            calculation_date=calculation_date,
            eligible=False,
            eligibility_reasons=(EligibilityReason.NO_EWA_POLICY,),
        )

    if not policy.enabled:
        return EWAResult(
            salary_amount_minor=salary_profile.monthly_salary_amount_minor,
            earned_amount_minor=0,
            policy_limit_minor=0,
            reserved_amount_minor=0,
            paid_amount_minor=0,
            available_amount_minor=0,
            pay_period_start=calculation_date,
            pay_period_end=calculation_date,
            calculation_date=calculation_date,
            eligible=False,
            eligibility_reasons=(EligibilityReason.EWA_DISABLED,),
        )

    # 5. Check minimum tenure
    if policy.minimum_tenure_days and policy.minimum_tenure_days > 0:
        tenure_start = employment.start_date
        if tenure_start:
            tenure_days = (calculation_date - tenure_start.date()).days
            if tenure_days < policy.minimum_tenure_days:
                return EWAResult(
                    salary_amount_minor=salary_profile.monthly_salary_amount_minor,
                    earned_amount_minor=0,
                    policy_limit_minor=0,
                    reserved_amount_minor=0,
                    paid_amount_minor=0,
                    available_amount_minor=0,
                    pay_period_start=calculation_date,
                    pay_period_end=calculation_date,
                    calculation_date=calculation_date,
                    eligible=False,
                    eligibility_reasons=(EligibilityReason.MINIMUM_TENURE_NOT_MET,),
                )

    # 6. Determine pay period
    pay_period_start, pay_period_end = _get_pay_period(calculation_date)

    # 6. Determine effective eligibility window
    effective_start = pay_period_start
    if employment.start_date:
        effective_start = max(effective_start, employment.start_date.date())
    if employment.eligible_from:
        effective_start = max(effective_start, employment.eligible_from.date())
    if salary_profile.effective_from:
        effective_start = max(effective_start, salary_profile.effective_from.date())

    effective_end = pay_period_end
    if employment.end_date:
        effective_end = min(effective_end, employment.end_date.date())
    if employment.eligible_to:
        effective_end = min(effective_end, employment.eligible_to.date())
    if salary_profile.effective_to:
        effective_end = min(effective_end, salary_profile.effective_to.date())

    # 7. Calculate earned amount
    earned_amount_minor = _calculate_earned(
        monthly_salary_minor=salary_profile.monthly_salary_amount_minor,
        pay_period_start=pay_period_start,
        pay_period_end=pay_period_end,
        effective_start=effective_start,
        effective_end=effective_end,
        calculation_date=calculation_date,
    )

    # 8. Calculate policy limit
    base_policy_limit = (earned_amount_minor * policy.max_access_percentage) // 100

    # Apply minimum remaining salary cap
    policy_limit = base_policy_limit
    if policy.minimum_remaining_salary_minor is not None:
        remaining_salary_cap = max(0, earned_amount_minor - policy.minimum_remaining_salary_minor)
        policy_limit = min(policy_limit, remaining_salary_cap)

    # 9. Get existing requests (reserved/paid)
    reserved_amount_minor, paid_amount_minor = await _get_existing_requests_summary(
        db, user_id, pay_period_start, pay_period_end
    )

    # 10. Calculate available
    consumed = reserved_amount_minor + paid_amount_minor
    available_amount_minor = max(0, policy_limit - consumed)

    # 11. Apply maximum withdrawal cap to requestable amount
    max_requestable = available_amount_minor
    if policy.maximum_withdrawal_minor is not None:
        max_requestable = min(max_requestable, policy.maximum_withdrawal_minor)

    # 12. Check minimum withdrawal
    can_request = True
    if policy.minimum_withdrawal_minor is not None and max_requestable < policy.minimum_withdrawal_minor:
        can_request = False

    return EWAResult(
        salary_amount_minor=salary_profile.monthly_salary_amount_minor,
        earned_amount_minor=earned_amount_minor,
        policy_limit_minor=policy_limit,
        reserved_amount_minor=reserved_amount_minor,
        paid_amount_minor=paid_amount_minor,
        available_amount_minor=available_amount_minor,
        pay_period_start=pay_period_start,
        pay_period_end=pay_period_end,
        calculation_date=calculation_date,
        eligible=True,
        eligibility_reasons=(),
        minimum_withdrawal_minor=policy.minimum_withdrawal_minor,
        maximum_withdrawal_minor=policy.maximum_withdrawal_minor,
        can_request_withdrawal=can_request,
    )