import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, JSON, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.types import GUID

PAYMENT_PROVIDERS = ("momo", "paypal")
PAYMENT_STATUSES = ("pending", "succeeded", "failed", "refunded", "cancelled")


class PaymentTransaction(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "payment_transactions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("subscriptions.id", ondelete="SET NULL")
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_transaction_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (CheckConstraint("amount > 0", name="ck_payment_amount_positive"),)


Index("ix_payments_user", PaymentTransaction.user_id)
Index("ix_payments_status", PaymentTransaction.status)