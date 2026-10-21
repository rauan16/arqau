from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class EmployeeCreate(BaseModel):
    user_id: str
    external_employee_id: Optional[str] = None
    display_name: Optional[str] = None
    status: Optional[str] = "active"


class EmployeeRead(BaseModel):
    id: str
    user_id: str
    external_employee_id: Optional[str] = None
    display_name: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class EmployeeUpdate(BaseModel):
    external_employee_id: Optional[str] = None
    display_name: Optional[str] = None
    status: Optional[str] = None
