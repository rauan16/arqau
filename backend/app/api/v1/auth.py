from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import timedelta
from app.database import get_db
from app.models import User, Onboarding, EarnedWages
from app.schemas.auth import UserRegister, UserLogin, UserResponse, TokenResponse, OnboardingData
from app.core.security import get_password_hash, verify_password, create_access_token, decode_access_token
from app.config import get_settings

settings = get_settings()
import uuid

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


@router.post("/register", response_model=TokenResponse)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    user = User(
        id=str(uuid.uuid4()),
        email=data.email,
        name=data.name,
        hashed_password=get_password_hash(data.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    access_token = create_access_token({"sub": user.id})
    return TokenResponse(access_token=access_token, token_type="bearer", user_id=user.id)


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive account")
    access_token = create_access_token({"sub": user.id})
    return TokenResponse(access_token=access_token, token_type="bearer", user_id=user.id)


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        is_verified=current_user.is_verified,
        is_active=current_user.is_active,
        created_at=current_user.created_at.isoformat() if current_user.created_at else "",
    )


@router.get("/onboarding", response_model=OnboardingData)
async def get_onboarding(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Onboarding).where(Onboarding.user_id == current_user.id))
    ob = result.scalar_one_or_none()
    if not ob:
        return OnboardingData()
    return OnboardingData(
        pay_frequency=ob.pay_frequency,
        monthly_income_range=ob.monthly_income_range,
        payday_range=ob.payday_range,
        financial_pressure=ob.financial_pressure,
        early_access_use_case=ob.early_access_use_case,
        ai_help_preference=ob.ai_help_preference,
    )


@router.put("/onboarding", response_model=OnboardingData)
async def save_onboarding(data: OnboardingData, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Onboarding).where(Onboarding.user_id == current_user.id))
    ob = result.scalar_one_or_none()
    if not ob:
        ob = Onboarding(id=str(uuid.uuid4()), user_id=current_user.id)
        db.add(ob)
    ob.pay_frequency = data.pay_frequency
    ob.monthly_income_range = data.monthly_income_range
    ob.payday_range = data.payday_range
    ob.financial_pressure = data.financial_pressure
    ob.early_access_use_case = data.early_access_use_case
    ob.ai_help_preference = data.ai_help_preference
    await db.commit()
    await db.refresh(ob)

    await _sync_demo_earned_wages(db, current_user.id, data.monthly_income_range)

    return OnboardingData(
        pay_frequency=ob.pay_frequency,
        monthly_income_range=ob.monthly_income_range,
        payday_range=ob.payday_range,
        financial_pressure=ob.financial_pressure,
        early_access_use_case=ob.early_access_use_case,
        ai_help_preference=ob.ai_help_preference,
    )


# ---------------------------------------------------------------------------
# Demo earned-wages initialization
# ---------------------------------------------------------------------------
# The portfolio demo needs a deterministic financial state so the pitch can
# show: Earned -> Available -> Recommendation -> Withdrawal -> What-if.
#
# These values are ILLUSTRATIVE DEMO DATA only. They are NOT derived from the
# user's real payroll and must never be treated as real earned wages.
#
# Source of truth: the canonical demo scenario in lib/demoData.ts
# (salary 300,000 KZT -> earned 187,400 KZT -> available 120,000 KZT).
# The mapping below keeps demo earned amounts proportional to that scenario.
# ---------------------------------------------------------------------------
_DEMO_EARNED_BY_INCOME_RANGE = {
    "Under 150,000": (93_700, 33_700),
    "150,000-300,000": (187_400, 67_400),
    "300,000-500,000": (312_300, 112_300),
    "500,000-750,000": (468_750, 168_750),
    "750,000+": (650_000, 233_000),
}


def _normalize_income_range(value: str | None) -> str | None:
    """Strip currency symbols and whitespace for robust lookup."""
    if not value:
        return None
    cleaned = value.replace("\u20b8", "").replace("\u2b2f", "").strip()
    # Collapse any whitespace introduced around the "+" suffix, e.g.
    # "750,000 +" -> "750,000+" so it matches the map key exactly.
    cleaned = cleaned.replace(" +", "+").replace("+ ", "+")
    return cleaned


async def _sync_demo_earned_wages(db, user_id: str, monthly_income_range: str | None):
    """Upsert the demo EarnedWages record for the user.

    - Creates the record if it does not exist.
    - Updates earned_amount_minor when onboarding income changes.
    - Preserves accessed_amount_minor (real withdrawal history) on update.
    - available_amount_minor is always derived: earned - accessed.
    """
    normalized = _normalize_income_range(monthly_income_range)
    demo = _DEMO_EARNED_BY_INCOME_RANGE.get(normalized) if normalized else None

    result = await db.execute(select(EarnedWages).where(EarnedWages.user_id == user_id))
    ew = result.scalar_one_or_none()

    if ew is None:
        earned = demo[0] if demo else 0
        accessed = demo[1] if demo else 0
        ew = EarnedWages(
            id=str(uuid.uuid4()),
            user_id=user_id,
            earned_amount_minor=earned,
            accessed_amount_minor=accessed,
            available_amount_minor=earned - accessed,
        )
        db.add(ew)
    else:
        # Only the earned target changes with the onboarding income range.
        # accessed_amount_minor is real withdrawal history and MUST be preserved.
        if demo:
            ew.earned_amount_minor = demo[0]
        ew.available_amount_minor = max(0, ew.earned_amount_minor - ew.accessed_amount_minor)

    await db.commit()
