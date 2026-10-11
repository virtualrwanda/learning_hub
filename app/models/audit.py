import uuid

from sqlalchemy import JSON, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.types import GUID


class AuditLog(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "audit_logs"

    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_entity_type: Mapped[str | None] = mapped_column(String(50))
    target_entity_id: Mapped[uuid.UUID | None] = mapped_column(GUID())
    previous_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    result: Mapped[str] = mapped_column(String(20), default="success", nullable=False)


Index("ix_audit_target", AuditLog.target_entity_type, AuditLog.target_entity_id)
Index("ix_audit_actor", AuditLog.actor_user_id)
Index("ix_audit_action", AuditLog.action)