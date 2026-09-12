from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class SalaryProfileCreate(BaseModel):
    employment_id: str
    currency: str = Field(..., min_length=3)
    monthly_salary_amount_minor: int = Field(..., gt=0)
    pay_schedule: Literal["monthly", "biweekly", "weekly", "other"] = "monthly"
    payday_day: Optional[int] = Field(None, ge=1, le=31)
    effective_from: datetime
    effective_to: Optional[datetime] = None

    @field_validator("effective_to")
    @classmethod
    def effective_to_after_effective_from(cls, value: Optional[datetime], info) -> Optional[datetime]:
        if value and value < info.data["effective_from"]:
            raise ValueError("effective_to must be after or equal to effective_from")
        return value


class SalaryProfileRead(BaseModel):
    id: str
    employment_id: str
    currency: str
    monthly_salary_amount_minor: int
    pay_schedule: str
    payday_day: Optional[int] = None
    effective_from: datetime
    effective_to: Optional[datetime] = None
    status: str
    source: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class SalaryProfileUpdate(BaseModel):
    currency: Optional[str] = None
    monthly_salary_amount_minor: Optional[int] = Field(None, gt=0)
    pay_schedule: Optional[Literal["monthly", "biweekly", "weekly", "other"]] = None
    payday_day: Optional[int] = Field(None, ge=1, le=31)
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None
    status: Optional[str] = None
    source: Optional[str] = None

    @field_validator("effective_to")
    @classmethod
    def effective_to_after_effective_from(cls, value: Optional[datetime], info) -> Optional[datetime]:
        if value and info.data.get("effective_from") and value < info.data["effective_from"]:
            raise ValueError("effective_to must be after or equal to effective_from")
        return value
