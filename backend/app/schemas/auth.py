from pydantic import BaseModel, EmailStr
from typing import Optional


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
    is_verified: bool
    is_active: bool
    created_at: str

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user_id: str


class OnboardingData(BaseModel):
    pay_frequency: Optional[str] = None
    monthly_income_range: Optional[str] = None
    payday_range: Optional[str] = None
    financial_pressure: Optional[str] = None
    early_access_use_case: Optional[str] = None
    ai_help_preference: Optional[str] = None
