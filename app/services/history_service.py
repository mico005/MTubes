import asyncio
from typing import Any
from fastapi import BackgroundTasks
from sqlalchemy.orm import Session
from app.db.models import PlayLog, MediaMetadata
from app.schemas import TrackRequest
from app.services.weight_service import enrich_tracks_with_scores
from app.services.common_service import (
    get_or_create_dummy_user,
    upsert_media_metadata,
    DUMMY_USER_ID,
)
from app.services.analysis_service import process_audio_features
from app.db.session import SessionLocal


def _is_features_already_extracted(db: Session, external_id: str) -> bool:
    media_record = db.query(MediaMetadata).filter(
        MediaMetadata.external_id == external_id
    ).first()
    return bool(media_record and media_record.features_extracted)


def _schedule_analysis_if_needed(
    db: Session,
    external_id: str,
    internal_id: Any,
    background_tasks: BackgroundTasks,
):
    if _is_features_already_extracted(db, external_id):
        return

    def run_extraction():
        bg_db = SessionLocal()
        try:
            asyncio.run(process_audio_features(
                bg_db, external_id, internal_id))
        finally:
            bg_db.close()

    background_tasks.add_task(run_extraction)


def log_track_play_with_analysis(
    db: Session,
    track: TrackRequest,
    background_tasks: BackgroundTasks,
):
    user_id = get_or_create_dummy_user(db)
    media_id = upsert_media_metadata(db, track)

    play_log = PlayLog(user_id=user_id, media_id=media_id)
    db.add(play_log)
    db.commit()

    _schedule_analysis_if_needed(db, track.id, media_id, background_tasks)


def log_track_play(db: Session, track: TrackRequest):
    user_id = get_or_create_dummy_user(db)
    media_id = upsert_media_metadata(db, track)

    play_log = PlayLog(user_id=user_id, media_id=media_id)
    db.add(play_log)
    db.commit()


def fetch_recent_history(db: Session, limit: int = 20) -> list[dict]:
    logs = (
        db.query(PlayLog, MediaMetadata)
        .join(MediaMetadata, PlayLog.media_id == MediaMetadata.id)
        .filter(PlayLog.user_id == DUMMY_USER_ID)
        .order_by(PlayLog.played_at.desc())
        .limit(limit)
        .all()
    )

    raw_tracks = [
        {
            "id": media.external_id,
            "title": media.title,
            "uploader": media.uploader,
            "thumbnail": media.thumbnail,
            "duration": media.duration,
        }
        for log, media in logs
    ]

    return enrich_tracks_with_scores(db, raw_tracks)
