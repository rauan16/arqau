from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AuditLogRead(BaseModel):
    id: str
    actor_user_id: Optional[str] = None
    employer_id: Optional[str] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    request_id: Optional[str] = None
    details: Optional[dict] = None
    before_data: Optional[dict] = None
    after_data: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}
