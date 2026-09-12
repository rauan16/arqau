from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class EmployerCreate(BaseModel):
    legal_name: str = Field(..., min_length=1)
    display_name: Optional[str] = None
    registration_number: Optional[str] = None
    country: Optional[str] = None


class EmployerRead(BaseModel):
    id: str
    legal_name: str
    display_name: Optional[str] = None
    registration_number: Optional[str] = None
    country: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class EmployerUpdate(BaseModel):
    legal_name: Optional[str] = None
    display_name: Optional[str] = None
    registration_number: Optional[str] = None
    country: Optional[str] = None
    status: Optional[str] = None

    @field_validator("legal_name")
    @classmethod
    def legal_name_must_not_be_empty(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError("legal_name cannot be empty or whitespace only")
        return value
