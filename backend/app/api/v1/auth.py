from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import timedelta
from app.database import get_db
from app.models import User, Onboarding, RefreshToken
from app.schemas.auth import (
    LogoutRequest,
    OnboardingData,
    RefreshRequest,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)
from app.services.audit_service import (
    LOGOUT,
    LOGOUT_ALL,
    LOGIN_FAILED,
    LOGIN_SUCCESS,
    REFRESH_ROTATED,
    record_audit_event,
)
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    decode_access_token,
    create_refresh_token,
    hash_refresh_token,
    make_family_id,
    role_from_user,
)
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
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive account")
    return user


async def _issue_tokens(db: AsyncSession, user: User) -> TokenResponse:
    access_token = create_access_token({"sub": user.id, "role": role_from_user(user)})
    plaintext, token_hash, expires_at = create_refresh_token(user.id)
    refresh_row = RefreshToken(
        id=str(uuid.uuid4()),
        user_id=user.id,
        token_hash=token_hash,
        family_id=make_family_id(),
        expires_at=expires_at,
    )
    db.add(refresh_row)
    await db.commit()
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        refresh_token=plaintext,
        role=role_from_user(user),
    )


@router.post("/register", response_model=TokenResponse)
async def register(data: UserRegister, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    existing = result.scalar_one_or_none()
    if existing:
        await record_audit_event(
            db,
            action=LOGIN_FAILED,
            metadata={"reason": "email_already_registered", "email": data.email},
        )
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
    await record_audit_event(
        db,
        actor_user_id=user.id,
        action=LOGIN_SUCCESS,
        entity_type="user",
        entity_id=user.id,
        metadata={"email": user.email},
    )
    return await _issue_tokens(db, user)


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.hashed_password):
        await record_audit_event(
            db,
            action=LOGIN_FAILED,
            metadata={"reason": "invalid_credentials", "email": data.email},
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        await record_audit_event(
            db,
            actor_user_id=user.id,
            action=LOGIN_FAILED,
            metadata={"reason": "inactive_account", "email": data.email},
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive account")
    await record_audit_event(
        db,
        actor_user_id=user.id,
        action=LOGIN_SUCCESS,
        entity_type="user",
        entity_id=user.id,
        metadata={"email": user.email},
    )
    return await _issue_tokens(db, user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    data: RefreshRequest = Body(...),
    db: AsyncSession = Depends(get_db),
):
    refresh_token = data.refresh_token
    token_hash = hash_refresh_token(refresh_token)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    if row.revoked_at is not None:
        # Reuse of a revoked/rotated token: fail closed and revoke the family.
        await _revoke_family(db, row.family_id)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked")
    if row.expires_at < _utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")
    user = await db.get(User, row.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    # Rotate: revoke old token, issue new one in the same family.
    row.revoked_at = _utcnow()
    row.last_used_at = _utcnow()
    plaintext, new_hash, new_expires = create_refresh_token(user.id)
    new_row = RefreshToken(
        id=str(uuid.uuid4()),
        user_id=user.id,
        token_hash=new_hash,
        family_id=row.family_id,
        rotated_from_id=row.id,
        expires_at=new_expires,
    )
    db.add(new_row)
    await record_audit_event(
        db,
        actor_user_id=user.id,
        action=REFRESH_ROTATED,
        entity_type="refresh_token",
        entity_id=new_row.id,
        metadata={"family_id": row.family_id},
    )
    await db.commit()

    access_token = create_access_token({"sub": user.id, "role": role_from_user(user)})
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        refresh_token=plaintext,
        role=role_from_user(user),
    )


@router.post("/logout")
async def logout(
    data: LogoutRequest = Body(...),
    db: AsyncSession = Depends(get_db),
):
    refresh_token = data.refresh_token
    token_hash = hash_refresh_token(refresh_token)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    row = result.scalar_one_or_none()
    if row and row.revoked_at is None:
        row.revoked_at = _utcnow()
        await record_audit_event(
            db,
            actor_user_id=row.user_id,
            action=LOGOUT,
            entity_type="refresh_token",
            entity_id=row.id,
        )
        await db.commit()
    return {"detail": "Logged out"}


@router.post("/logout-all")
async def logout_all(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == current_user.id,
            RefreshToken.revoked_at.is_(None),
        )
    )
    rows = list(result.scalars().all())
    now = _utcnow()
    for row in rows:
        row.revoked_at = now
    await record_audit_event(
        db,
        actor_user_id=current_user.id,
        action=LOGOUT_ALL,
        metadata={"revoked_count": len(rows)},
    )
    await db.commit()
    return {"detail": "All sessions revoked"}


async def _revoke_family(db: AsyncSession, family_id: str) -> None:
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.family_id == family_id,
            RefreshToken.revoked_at.is_(None),
        )
    )
    now = _utcnow()
    for row in result.scalars().all():
        row.revoked_at = now
    await db.commit()


def _utcnow():
    from datetime import datetime
    return datetime.utcnow()


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

    return OnboardingData(
        pay_frequency=ob.pay_frequency,
        monthly_income_range=ob.monthly_income_range,
        payday_range=ob.payday_range,
        financial_pressure=ob.financial_pressure,
        early_access_use_case=ob.early_access_use_case,
        ai_help_preference=ob.ai_help_preference,
    )