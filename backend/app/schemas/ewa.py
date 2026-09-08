from pydantic import BaseModel
from typing import Optional


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
