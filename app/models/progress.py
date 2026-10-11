import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.types import GUID

PROGRESS_STATES = ("not_started", "in_progress", "completed")


class LearningProgress(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "learning_progress"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="not_started", nullable=False)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_position_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "lesson_id", name="uq_progress_user_lesson"),)


class VideoWatchSession(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "video_watch_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    video_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    seconds_watched: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    device_info: Mapped[str | None] = mapped_column(String(255))


class UserActivity(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "user_activity"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


Index("ix_progress_user", LearningProgress.user_id)
Index("ix_watch_user_video", VideoWatchSession.user_id, VideoWatchSession.video_id)
Index("ix_activity_user_type", UserActivity.user_id, UserActivity.event_type)
Index("ix_activity_occurred", UserActivity.occurred_at)