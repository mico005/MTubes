from sqlalchemy import Column, String, DateTime, Float, ForeignKey, Integer, Boolean
from sqlalchemy.types import Uuid
from sqlalchemy.sql import func
import uuid
from app.db.session import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    username = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MediaMetadata(Base):
    __tablename__ = "media_metadata"
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    external_id = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=False)
    uploader = Column(String, nullable=True)
    thumbnail = Column(String, nullable=True)
    duration = Column(Integer, nullable=False, default=0)
    extracted_at = Column(DateTime(timezone=True), server_default=func.now())

    energy = Column(Float, nullable=True)
    danceability = Column(Float, nullable=True)
    acousticness = Column(Float, nullable=True)
    features_extracted = Column(Boolean, nullable=False, default=False)


class PlayLog(Base):
    __tablename__ = "play_logs"
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid, ForeignKey("users.id"), nullable=False)
    media_id = Column(Uuid, ForeignKey("media_metadata.id"), nullable=False)
    play_duration_seconds = Column(Float, nullable=False, default=0.0)
    played_at = Column(DateTime(timezone=True), server_default=func.now())


class WeightScore(Base):
    __tablename__ = "weight_scores"
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid, ForeignKey("users.id"), nullable=False)
    external_id = Column(String, index=True, nullable=False)

    base_score = Column(Float, nullable=False, default=0.0)
    is_favorited = Column(Boolean, nullable=False, default=False)
    is_trashed = Column(Boolean, nullable=False, default=False)

    updated_at = Column(DateTime(timezone=True),
                        server_default=func.now(), onupdate=func.now())
    last_played_at = Column(DateTime(timezone=True), server_default=func.now())


class Playlist(Base):
    __tablename__ = "playlists"
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PlaylistTrack(Base):
    __tablename__ = "playlist_tracks"
    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    playlist_id = Column(Uuid, ForeignKey(
        "playlists.id", ondelete="CASCADE"), nullable=False)
    media_id = Column(Uuid, ForeignKey("media_metadata.id"), nullable=False)
    added_at = Column(DateTime(timezone=True), server_default=func.now())
