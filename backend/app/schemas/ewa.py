from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class EarnedWagesResponse(BaseModel):
    id: str
    user_id: str
    earned_amount_minor: int
    accessed_amount_minor: int
    available_amount_minor: int
    period_start: Optional[str] = None
    period_end: Optional[str] = None

    model_config = {"from_attributes": True}


class EarnedWagesUpdate(BaseModel):
    earned_amount_minor: int


class AvailableResponse(BaseModel):
    available_amount_minor: int


class WageAccessRequestCreate(BaseModel):
    amount_minor: int
    reason: Optional[str] = None


class WageAccessRequestResponse(BaseModel):
    id: str
    user_id: str
    amount_minor: int
    status: str
    reason: Optional[str] = None
    created_at: str

    model_config = {"from_attributes": True}


class EwaPolicyBase(BaseModel):
    enabled: bool = True
    max_access_percentage: int = Field(..., ge=0, le=100)
    max_withdrawals_per_period: Optional[int] = Field(None, ge=0)
    minimum_tenure_days: Optional[int] = Field(None, ge=0)
    minimum_remaining_salary_minor: Optional[int] = Field(None, ge=0)
    minimum_withdrawal_minor: Optional[int] = Field(None, ge=0)
    maximum_withdrawal_minor: Optional[int] = Field(None, ge=0)

    @field_validator("maximum_withdrawal_minor")
    @classmethod
    def max_withdrawal_ge_min(cls, value: Optional[int], info) -> Optional[int]:
        min_withdrawal = info.data.get("minimum_withdrawal_minor")
        if value is not None and min_withdrawal is not None and value < min_withdrawal:
            raise ValueError("maximum_withdrawal_minor must be >= minimum_withdrawal_minor")
        return value


class EwaPolicyCreate(EwaPolicyBase):
    pass


class EwaPolicyUpdate(EwaPolicyBase):
    enabled: Optional[bool] = None
    max_access_percentage: Optional[int] = Field(None, ge=0, le=100)
    max_withdrawals_per_period: Optional[int] = Field(None, ge=0)
    minimum_tenure_days: Optional[int] = Field(None, ge=0)
    minimum_remaining_salary_minor: Optional[int] = Field(None, ge=0)
    minimum_withdrawal_minor: Optional[int] = Field(None, ge=0)
    maximum_withdrawal_minor: Optional[int] = Field(None, ge=0)


class EwaPolicyRead(BaseModel):
    id: str
    employer_id: str
    enabled: bool
    max_access_percentage: int
    max_withdrawals_per_period: Optional[int] = None
    minimum_tenure_days: Optional[int] = None
    minimum_remaining_salary_minor: Optional[int] = None
    minimum_withdrawal_minor: Optional[int] = None
    maximum_withdrawal_minor: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
