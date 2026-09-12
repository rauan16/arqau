from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class EmploymentCreate(BaseModel):
    employee_id: str
    employer_id: str
    employment_type: Optional[str] = None
    status: Optional[str] = "active"
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    eligible_from: Optional[datetime] = None
    eligible_to: Optional[datetime] = None

    @field_validator("end_date")
    @classmethod
    def end_date_after_start_date(cls, value: Optional[datetime], info) -> Optional[datetime]:
        if value and info.data.get("start_date") and value < info.data["start_date"]:
            raise ValueError("end_date must be after or equal to start_date")
        return value

    @field_validator("eligible_to")
    @classmethod
    def eligible_to_after_eligible_from(cls, value: Optional[datetime], info) -> Optional[datetime]:
        if value and info.data.get("eligible_from") and value < info.data["eligible_from"]:
            raise ValueError("eligible_to must be after or equal to eligible_from")
        return value


class EmploymentRead(BaseModel):
    id: str
    employee_id: str
    employer_id: str
    employment_type: Optional[str] = None
    status: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    eligible_from: Optional[datetime] = None
    eligible_to: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class EmploymentUpdate(BaseModel):
    employment_type: Optional[str] = None
    status: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    eligible_from: Optional[datetime] = None
    eligible_to: Optional[datetime] = None

    @field_validator("end_date")
    @classmethod
    def end_date_after_start_date(cls, value: Optional[datetime], info) -> Optional[datetime]:
        if value and info.data.get("start_date") and value < info.data["start_date"]:
            raise ValueError("end_date must be after or equal to start_date")
        return value

    @field_validator("eligible_to")
    @classmethod
    def eligible_to_after_eligible_from(cls, value: Optional[datetime], info) -> Optional[datetime]:
        if value and info.data.get("eligible_from") and value < info.data["eligible_from"]:
            raise ValueError("eligible_to must be after or equal to eligible_from")
        return value
