from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import String, Integer, BigInteger, Float, Boolean, DateTime, JSON, ForeignKey, Text, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

def uid(): return uuid4().hex

def now(): return datetime.now(timezone.utc)

class Upload(Base):
    __tablename__ = 'uploads'
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=uid)
    filename: Mapped[str] = mapped_column(String(255))
    size: Mapped[int] = mapped_column(BigInteger)
    offset: Mapped[int] = mapped_column(BigInteger, default=0)
    expected_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rights_confirmed: Mapped[bool] = mapped_column(Boolean)
    status: Mapped[str] = mapped_column(String(30), default='uploading')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Media(Base):
    __tablename__ = 'media'
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=uid)
    filename: Mapped[str] = mapped_column(String(255))
    source_path: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(BigInteger)
    duration: Mapped[float] = mapped_column(Float)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    fps: Mapped[float] = mapped_column(Float)
    has_audio: Mapped[bool] = mapped_column(Boolean)
    youtube_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Job(Base):
    __tablename__ = 'jobs'
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=uid)
    media_id: Mapped[str] = mapped_column(String(40), ForeignKey('media.id'))
    clip_id: Mapped[str | None] = mapped_column(String(40), ForeignKey('clips.id'), nullable=True)
    kind: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(25), default='queued')
    stage: Mapped[str] = mapped_column(String(80), default='queued')
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    heartbeat: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled: Mapped[bool] = mapped_column(Boolean, default=False)

class Clip(Base):
    __tablename__ = 'clips'
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=uid)
    media_id: Mapped[str] = mapped_column(String(40), ForeignKey('media.id'))
    title: Mapped[str] = mapped_column(String(180), default='Untitled clip')
    segments: Mapped[list] = mapped_column(JSON)
    reasoning: Mapped[str] = mapped_column(Text, default='Manually selected')
    origin: Mapped[str] = mapped_column(String(30), default='manual')
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    options: Mapped[dict] = mapped_column(JSON, default=dict)
    output_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)