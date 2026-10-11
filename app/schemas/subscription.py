from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.subscription import SUBSCRIPTION_STATES


class SubscriptionPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    plan_id: UUID | None
    status: str
    start_date: datetime | None
    end_date: datetime | None
    created_at: datetime
    updated_at: datetime


class SubscriptionPlanCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    price_usd: float = Field(gt=0)
    duration_days: int = Field(gt=0, le=3650)
    is_active: bool = True


class SubscriptionPlanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    price_usd: float | None = Field(default=None, gt=0)
    duration_days: int | None = Field(default=None, gt=0, le=3650)
    is_active: bool | None = None


class SubscriptionPlanPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    price_usd: float
    duration_days: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SubscriptionCreate(BaseModel):
    """Student starts a subscription — plan chosen, payment to follow."""

    plan_id: UUID


# ------------------------------------------------------------------
# Admin actions
# ------------------------------------------------------------------
class SubscriptionManualActivate(BaseModel):
    plan_id: UUID | None = None
    duration_days: int | None = Field(default=None, gt=0, le=3650)
    reason: str = Field(min_length=3, max_length=500)


class SubscriptionExtend(BaseModel):
    days: int = Field(gt=0, le=3650)
    reason: str = Field(min_length=3, max_length=500)


class SubscriptionSuspend(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class SubscriptionCancel(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class SubscriptionSetExpiry(BaseModel):
    end_date: datetime
    reason: str = Field(min_length=3, max_length=500)