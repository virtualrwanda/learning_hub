import uuid

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPKMixin
from app.db.types import GUID

ALLOW_DOWNLOAD_SCOPES = (
    "disabled",
    "selected_users",
    "selected_courses",
    "selected_videos",
    "enabled",
)

VIDEO_STATUSES = ("uploading", "processing", "ready", "failed")

DOCUMENT_TYPES = ("notes", "exercise", "past_exam", "solution", "supplementary")


class Video(Base, UUIDPKMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "videos"

    lesson_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False
    )
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="uploading", nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(String(500))
    allow_download: Mapped[str] = mapped_column(String(20), default="disabled", nullable=False)


class VideoRendition(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "video_renditions"

    video_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False
    )
    resolution: Mapped[str] = mapped_column(String(20), nullable=False)
    bitrate: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)


class Document(Base, UUIDPKMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "documents"

    lesson_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    allow_download: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


Index("ix_videos_lesson", Video.lesson_id)
Index("ix_videos_status", Video.status)
Index("ix_renditions_video", VideoRendition.video_id)
Index("ix_documents_lesson", Document.lesson_id)
Index("ix_documents_type", Document.type)