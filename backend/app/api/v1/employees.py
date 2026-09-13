from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Employee, User
from app.schemas.employee import EmployeeCreate, EmployeeRead
from app.services.audit_service import EMPLOYEE_CREATED, record_audit_event
from app.services.employee_service import create_employee as create_employee_service
from app.api.v1.auth import get_current_user
from app.core.authorization import (
    assert_employee_access,
    is_super_admin,
    get_employer_scope,
    is_employee,
    _user_has_scope,
)
from app.models import Employment

router = APIRouter(prefix="/employees", tags=["employee"])


@router.post("/", response_model=EmployeeRead)
async def create_employee(
    data: EmployeeCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    is_self_service = data.user_id == current_user.id

    # Arbitrary employee creation: validate the target user exists first so we
    # return a controlled 400 (matching service semantics) before any
    # authorization decision.
    if not is_self_service:
        target_user = await db.get(User, data.user_id)
        if not target_user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not found")
        if not (is_super_admin(current_user) or await _user_has_scope(current_user, db)):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    try:
        employee = await create_employee_service(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    await record_audit_event(
        db,
        actor_user_id=current_user.id,
        action=EMPLOYEE_CREATED,
        entity_type="employee",
        entity_id=employee.id,
        metadata={"user_id": employee.user_id, "self_service": is_self_service},
    )
    await db.commit()
    await db.refresh(employee)
    return employee


@router.get("/{employee_id}", response_model=EmployeeRead)
async def get_employee(
    employee_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await assert_employee_access(current_user, db, employee_id)