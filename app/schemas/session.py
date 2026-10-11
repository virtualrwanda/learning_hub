from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SessionInfo(BaseModel):
    user_id: UUID
    email: str
    session_active: bool = True
    last_activity_at: datetime | None = None
    expires_at: datetime | None = None