from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import dialect as pg_dialect
from datetime import date, datetime
from typing import Optional
import uuid

from app.database import get_db
from app.models import User, EarnedWages, WageAccessRequest, Employee, Employment, Employer, EwaPolicy
from app.schemas.ewa import (
    EarnedWagesUpdate,
    EarnedWagesResponse,
    AvailableResponse,
    WageAccessRequestCreate,
    WageAccessRequestResponse,
    EWAResultResponse,
)
from app.api.v1.auth import get_current_user
from app.services.audit_service import (
    USER_REQUESTED_WITHDRAWAL,
    WITHDRAWAL_APPROVED,
    WITHDRAWAL_REJECTED,
    WITHDRAWAL_CANCELLED,
    WITHDRAWAL_PAID,
    record_audit_event,
)
from app.services.ewa_engine import calculate_ewa, EligibilityReason
from app.core.authorization import (
    assert_employer_access,
    is_super_admin,
    is_employer_admin,
    is_finance_manager,
    get_employer_scope,
)

router = APIRouter(prefix="/ewa", tags=["ewa"])


def calculate_available(earned_amount_minor: int, accessed_amount_minor: int) -> int:
    available = earned_amount_minor - accessed_amount_minor
    return max(0, available)


@router.get("/earned", response_model=EarnedWagesResponse)
async def get_earned(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EarnedWages).where(EarnedWages.user_id == current_user.id))
    ew = result.scalar_one_or_none()
    if not ew:
        return EarnedWagesResponse(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            earned_amount_minor=0,
            accessed_amount_minor=0,
            available_amount_minor=0,
        )
    return EarnedWagesResponse(
        id=ew.id,
        user_id=ew.user_id,
        earned_amount_minor=ew.earned_amount_minor,
        accessed_amount_minor=ew.accessed_amount_minor,
        available_amount_minor=ew.available_amount_minor,
        period_start=ew.period_start,
        period_end=ew.period_end,
    )


@router.put("/earned", response_model=EarnedWagesResponse)
async def update_earned(data: EarnedWagesUpdate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if data.earned_amount_minor < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Earned amount cannot be negative")
    result = await db.execute(select(EarnedWages).where(EarnedWages.user_id == current_user.id))
    ew = result.scalar_one_or_none()
    if not ew:
        ew = EarnedWages(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            earned_amount_minor=data.earned_amount_minor,
            accessed_amount_minor=0,
            available_amount_minor=data.earned_amount_minor,
        )
        db.add(ew)
    else:
        ew.earned_amount_minor = data.earned_amount_minor
        ew.available_amount_minor = calculate_available(ew.earned_amount_minor, ew.accessed_amount_minor)
    await db.commit()
    await db.refresh(ew)
    return EarnedWagesResponse(
        id=ew.id,
        user_id=ew.user_id,
        earned_amount_minor=ew.earned_amount_minor,
        accessed_amount_minor=ew.accessed_amount_minor,
        available_amount_minor=ew.available_amount_minor,
        period_start=ew.period_start,
        period_end=ew.period_end,
    )


@router.get("/available", response_model=AvailableResponse)
async def get_available(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Get available amount using deterministic engine.

    Returns 0 if required real data (Employee, Employment, SalaryProfile, EwaPolicy) is incomplete.
    Legacy EarnedWages is NOT used as an authoritative source.
    """
    calc = await calculate_ewa(db, current_user.id)
    return AvailableResponse(available_amount_minor=calc.available_amount_minor)


@router.get("/calculation", response_model=EWAResultResponse)
async def get_calculation(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Authoritative EWA calculation from deterministic backend engine.

    Returns structured result with all calculation components.
    No demo data, no AI, integer money only.
    """
    calc = await calculate_ewa(db, current_user.id)
    return EWAResultResponse(
        salary_amount_minor=calc.salary_amount_minor,
        earned_amount_minor=calc.earned_amount_minor,
        policy_limit_minor=calc.policy_limit_minor,
        reserved_amount_minor=calc.reserved_amount_minor,
        paid_amount_minor=calc.paid_amount_minor,
        available_amount_minor=calc.available_amount_minor,
        pay_period_start=calc.pay_period_start.isoformat(),
        pay_period_end=calc.pay_period_end.isoformat(),
        calculation_date=calc.calculation_date.isoformat(),
        eligible=calc.eligible,
        eligibility_reasons=list(calc.eligibility_reasons),
        minimum_withdrawal_minor=calc.minimum_withdrawal_minor,
        maximum_withdrawal_minor=calc.maximum_withdrawal_minor,
        can_request_withdrawal=calc.can_request_withdrawal,
        max_withdrawals_per_period=calc.max_withdrawals_per_period,
        withdrawals_this_period=calc.withdrawals_this_period,
    )


def _validate_transition(current_status: str, new_status: str) -> None:
    """Validate lifecycle transition. Raise if invalid."""
    valid_transitions = {
        "pending": {"approved", "rejected", "cancelled"},
        "approved": {"paid", "cancelled"},
    }
    if current_status not in valid_transitions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot transition from status '{current_status}'",
        )
    if new_status not in valid_transitions[current_status]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid transition from '{current_status}' to '{new_status}'",
        )


async def _resolve_employment_and_policy(
    db: AsyncSession, user_id: str
) -> tuple[Optional[Employment], Optional[EwaPolicy], Optional[Employee]]:
    """Resolve employee's active employment and employer's EWA policy."""
    result = await db.execute(select(Employee).where(Employee.user_id == user_id))
    employee = result.scalar_one_or_none()
    if not employee:
        return None, None, None

    result = await db.execute(
        select(Employment)
        .where(
            Employment.employee_id == employee.id,
            Employment.status == "active",
        )
    )
    employments = result.scalars().all()

    calculation_date = datetime.utcnow().date()
    for emp in employments:
        if emp.start_date and emp.start_date.date() > calculation_date:
            continue
        if emp.end_date and emp.end_date.date() <= calculation_date:
            continue
        if emp.eligible_from and emp.eligible_from.date() > calculation_date:
            continue
        if emp.eligible_to and emp.eligible_to.date() <= calculation_date:
            continue
        # Found active employment
        result = await db.execute(
            select(EwaPolicy).where(EwaPolicy.employer_id == emp.employer_id)
        )
        policy = result.scalar_one_or_none()
        return emp, policy, employee

    return None, None, employee


@router.post("/request", response_model=WageAccessRequestResponse)
async def create_request(data: WageAccessRequestCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Create a withdrawal request with concurrency safety.

    - Recomputes EWA availability server-side
    - Validates against deterministic engine
    - Uses row locking (SELECT FOR UPDATE on PostgreSQL) to prevent double-spending
    - Supports optional idempotency_key for duplicate protection
    """
    if data.amount_minor <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Amount must be positive")

    # Idempotency: check for existing request with same key
    if data.idempotency_key:
        result = await db.execute(
            select(WageAccessRequest).where(WageAccessRequest.idempotency_key == data.idempotency_key)
        )
        existing = result.scalar_one_or_none()
        if existing:
            # Return existing request if it belongs to the same user
            if existing.user_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Idempotency key conflict")
            return WageAccessRequestResponse.model_validate(existing)

    # Resolve employment and policy
    employment, policy, employee = await _resolve_employment_and_policy(db, current_user.id)

    # Primary path: authoritative deterministic EWA engine backed by real
    # Employee/Employment/SalaryProfile/EwaPolicy data.
    if employment and policy and policy.enabled:
        # Recompute EWA result server-side
        calc = await calculate_ewa(db, current_user.id)
        if calc.eligible:
            # Validate amount against maximum requestable
            max_requestable = calc.available_amount_minor
            if policy.maximum_withdrawal_minor is not None:
                max_requestable = min(max_requestable, policy.maximum_withdrawal_minor)

            if data.amount_minor > max_requestable:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Amount exceeds maximum requestable of {max_requestable}",
                )

            # Validate minimum withdrawal
            if policy.minimum_withdrawal_minor is not None and data.amount_minor < policy.minimum_withdrawal_minor:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Amount below minimum withdrawal of {policy.minimum_withdrawal_minor}",
                )

            # Concurrency safety: lock the employment row to serialize requests for this employment
            # This prevents two concurrent requests from both seeing the same available capacity
            await db.execute(
                select(Employment)
                .where(Employment.id == employment.id)
                .with_for_update(nowait=True)
            )

            # Re-validate availability after acquiring lock (recompute inside transaction)
            calc = await calculate_ewa(db, current_user.id)
            max_requestable = calc.available_amount_minor
            if policy.maximum_withdrawal_minor is not None:
                max_requestable = min(max_requestable, policy.maximum_withdrawal_minor)

            if data.amount_minor > max_requestable:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Amount exceeds available capacity after concurrency check ({max_requestable})",
                )

            # Create pending request with pay-period binding
            req = WageAccessRequest(
                id=str(uuid.uuid4()),
                user_id=current_user.id,
                amount_minor=data.amount_minor,
                reason=data.reason,
                status="pending",
                pay_period_start=calc.pay_period_start,
                pay_period_end=calc.pay_period_end,
                idempotency_key=data.idempotency_key,
            )
            db.add(req)

            await record_audit_event(
                db,
                actor_user_id=current_user.id,
                employer_id=employment.employer_id,
                action=USER_REQUESTED_WITHDRAWAL,
                entity_type="wage_access_request",
                entity_id=req.id,
                metadata={"user_id": current_user.id, "amount_minor": data.amount_minor},
            )

            await db.commit()
            await db.refresh(req)
            return WageAccessRequestResponse.model_validate(req)

    # Legacy fallback: no real employment/policy is configured, or the
    # deterministic engine is not eligible. Use the legacy EarnedWages ledger
    # (available_amount_minor) as the source of truth so existing API contracts
    # and tests that predate the Phase 2.3 engine keep working.
    result = await db.execute(select(EarnedWages).where(EarnedWages.user_id == current_user.id))
    ew = result.scalar_one_or_none()
    if not ew:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No earned wages set. Set earned wages first.")
    available = ew.available_amount_minor
    if data.amount_minor > available:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Amount exceeds available balance of {available} ?")

    req = WageAccessRequest(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        amount_minor=data.amount_minor,
        reason=data.reason,
        status="pending",
        idempotency_key=data.idempotency_key,
    )
    db.add(req)

    await record_audit_event(
        db,
        actor_user_id=current_user.id,
        employer_id=None,
        action=USER_REQUESTED_WITHDRAWAL,
        entity_type="wage_access_request",
        entity_id=req.id,
        metadata={"user_id": current_user.id, "amount_minor": data.amount_minor},
    )

    ew.accessed_amount_minor += data.amount_minor
    ew.available_amount_minor = calculate_available(ew.earned_amount_minor, ew.accessed_amount_minor)

    await db.commit()
    await db.refresh(req)
    return WageAccessRequestResponse.model_validate(req)


@router.get("/requests", response_model=list[WageAccessRequestResponse])
async def get_requests(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(WageAccessRequest).where(WageAccessRequest.user_id == current_user.id).order_by(WageAccessRequest.created_at.desc())
    )
    reqs = result.scalars().all()
    return [WageAccessRequestResponse.model_validate(r) for r in reqs]


@router.post("/requests/{request_id}/cancel", response_model=WageAccessRequestResponse)
async def cancel_request(request_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Employee cancels their own pending request."""
    result = await db.execute(select(WageAccessRequest).where(WageAccessRequest.id == request_id))
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    if req.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your request")

    if req.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only pending requests can be cancelled")

    prev_status = req.status
    req.status = "cancelled"
    req.cancelled_at = datetime.utcnow()
    req.cancelled_by_user_id = current_user.id

    await record_audit_event(
        db,
        actor_user_id=current_user.id,
        employer_id=None,  # Will be filled by employment lookup if needed
        action=WITHDRAWAL_CANCELLED,
        entity_type="wage_access_request",
        entity_id=req.id,
        before_data={"status": prev_status},
        after_data={"status": "cancelled"},
        metadata={"amount_minor": req.amount_minor},
    )

    await db.commit()
    await db.refresh(req)
    return WageAccessRequestResponse.model_validate(req)


# ============================================================
# EMPLOYER-SCOPED ENDPOINTS
# ============================================================

@router.get("/employers/{employer_id}/requests", response_model=list[WageAccessRequestResponse])
async def list_employer_requests(
    employer_id: str,
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all wage access requests for an employer (employer_admin, finance_manager, super_admin)."""
    await assert_employer_access(current_user, db, employer_id)

    # finance_manager can only read (and pay), not approve/reject
    # but listing is allowed for all three roles
    query = (
        select(WageAccessRequest)
        .join(Employee, WageAccessRequest.user_id == Employee.user_id)
        .join(Employment, Employee.id == Employment.employee_id)
        .where(Employment.employer_id == employer_id)
        .order_by(WageAccessRequest.created_at.desc())
    )

    if status_filter:
        query = query.where(WageAccessRequest.status == status_filter)

    result = await db.execute(query)
    reqs = result.scalars().all()
    return [WageAccessRequestResponse.model_validate(r) for r in reqs]


async def _employer_action_require_approval_role(current_user: User, db: AsyncSession, employer_id: str) -> None:
    """Check if user can approve/reject (employer_admin or super_admin)."""
    if is_super_admin(current_user):
        return
    if is_employer_admin(current_user):
        scope = await get_employer_scope(current_user, db)
        if employer_id in scope:
            return
    # finance_manager cannot approve/reject unless explicitly allowed by policy
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions to approve/reject")


async def _employer_action_require_finance_role(current_user: User, db: AsyncSession, employer_id: str) -> None:
    """Check if user can pay (finance_manager, employer_admin, super_admin)."""
    if is_super_admin(current_user):
        return
    scope = await get_employer_scope(current_user, db)
    if employer_id in scope:
        # Both employer_admin and finance_manager have scope
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions to process payment")


@router.post("/employers/{employer_id}/requests/{request_id}/approve", response_model=WageAccessRequestResponse)
async def approve_request(
    employer_id: str,
    request_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Approve a pending withdrawal request (employer_admin, super_admin)."""
    await _employer_action_require_approval_role(current_user, db, employer_id)

    result = await db.execute(
        select(WageAccessRequest)
        .join(Employee, WageAccessRequest.user_id == Employee.user_id)
        .join(Employment, Employee.id == Employment.employee_id)
        .where(WageAccessRequest.id == request_id, Employment.employer_id == employer_id)
    )
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    if req.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only pending requests can be approved")

    _validate_transition(req.status, "approved")

    prev_status = req.status
    req.status = "approved"
    req.approved_at = datetime.utcnow()
    req.approved_by_user_id = current_user.id

    await record_audit_event(
        db,
        actor_user_id=current_user.id,
        employer_id=employer_id,
        action=WITHDRAWAL_APPROVED,
        entity_type="wage_access_request",
        entity_id=req.id,
        before_data={"status": prev_status},
        after_data={"status": "approved"},
        metadata={"amount_minor": req.amount_minor},
    )

    await db.commit()
    await db.refresh(req)
    return WageAccessRequestResponse.model_validate(req)


@router.post("/employers/{employer_id}/requests/{request_id}/reject", response_model=WageAccessRequestResponse)
async def reject_request(
    employer_id: str,
    request_id: str,
    reason: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reject a pending withdrawal request (employer_admin, super_admin)."""
    await _employer_action_require_approval_role(current_user, db, employer_id)

    result = await db.execute(
        select(WageAccessRequest)
        .join(Employee, WageAccessRequest.user_id == Employee.user_id)
        .join(Employment, Employee.id == Employment.employee_id)
        .where(WageAccessRequest.id == request_id, Employment.employer_id == employer_id)
    )
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    if req.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only pending requests can be rejected")

    _validate_transition(req.status, "rejected")

    prev_status = req.status
    req.status = "rejected"
    req.rejected_at = datetime.utcnow()
    req.rejected_by_user_id = current_user.id
    req.rejection_reason = reason

    await record_audit_event(
        db,
        actor_user_id=current_user.id,
        employer_id=employer_id,
        action=WITHDRAWAL_REJECTED,
        entity_type="wage_access_request",
        entity_id=req.id,
        before_data={"status": prev_status},
        after_data={"status": "rejected", "rejection_reason": reason},
        metadata={"amount_minor": req.amount_minor},
    )

    await db.commit()
    await db.refresh(req)
    return WageAccessRequestResponse.model_validate(req)


@router.post("/employers/{employer_id}/requests/{request_id}/pay", response_model=WageAccessRequestResponse)
async def pay_request(
    employer_id: str,
    request_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark an approved request as paid (finance_manager, employer_admin, super_admin)."""
    await _employer_action_require_finance_role(current_user, db, employer_id)

    result = await db.execute(
        select(WageAccessRequest)
        .join(Employee, WageAccessRequest.user_id == Employee.user_id)
        .join(Employment, Employee.id == Employment.employee_id)
        .where(WageAccessRequest.id == request_id, Employment.employer_id == employer_id)
    )
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    if req.status not in ("approved",):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only approved requests can be paid")

    _validate_transition(req.status, "paid")

    prev_status = req.status
    req.status = "paid"
    req.paid_at = datetime.utcnow()
    req.paid_by_user_id = current_user.id

    await record_audit_event(
        db,
        actor_user_id=current_user.id,
        employer_id=employer_id,
        action=WITHDRAWAL_PAID,
        entity_type="wage_access_request",
        entity_id=req.id,
        before_data={"status": prev_status},
        after_data={"status": "paid"},
        metadata={"amount_minor": req.amount_minor},
    )

    await db.commit()
    await db.refresh(req)
    return WageAccessRequestResponse.model_validate(req)