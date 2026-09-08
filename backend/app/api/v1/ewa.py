from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import User, EarnedWages, WageAccessRequest
from app.schemas.ewa import EarnedWagesUpdate, EarnedWagesResponse, AvailableResponse, WageAccessRequestCreate, WageAccessRequestResponse
from app.api.v1.auth import get_current_user
import uuid

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
    result = await db.execute(select(EarnedWages).where(EarnedWages.user_id == current_user.id))
    ew = result.scalar_one_or_none()
    if not ew:
        return AvailableResponse(available_amount_minor=0)
    return AvailableResponse(available_amount_minor=ew.available_amount_minor)


@router.post("/request", response_model=WageAccessRequestResponse)
async def create_request(data: WageAccessRequestCreate, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if data.amount_minor <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Amount must be positive")
    result = await db.execute(select(EarnedWages).where(EarnedWages.user_id == current_user.id))
    ew = result.scalar_one_or_none()
    if not ew:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No earned wages set. Set earned wages first.")
    available = ew.available_amount_minor
    if data.amount_minor > available:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Amount exceeds available balance of {available} ₸")
    req = WageAccessRequest(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        amount_minor=data.amount_minor,
        reason=data.reason,
        status="pending",
    )
    db.add(req)
    ew.accessed_amount_minor += data.amount_minor
    ew.available_amount_minor = calculate_available(ew.earned_amount_minor, ew.accessed_amount_minor)
    await db.commit()
    await db.refresh(req)
    return WageAccessRequestResponse(
        id=req.id,
        user_id=req.user_id,
        amount_minor=req.amount_minor,
        status=req.status,
        reason=req.reason,
        created_at=req.created_at.isoformat() if req.created_at else "",
    )


@router.get("/requests", response_model=list[WageAccessRequestResponse])
async def get_requests(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(WageAccessRequest).where(WageAccessRequest.user_id == current_user.id).order_by(WageAccessRequest.created_at.desc())
    )
    reqs = result.scalars().all()
    return [
        WageAccessRequestResponse(
            id=r.id,
            user_id=r.user_id,
            amount_minor=r.amount_minor,
            status=r.status,
            reason=r.reason,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in reqs
    ]
