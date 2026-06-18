from sqlalchemy.orm import Session
from app.db.models import PlayLog, MediaMetadata
from app.schemas import TrackRequest
from app.services.weight_service import enrich_tracks_with_scores
from app.services.common_service import get_or_create_dummy_user, upsert_media_metadata, DUMMY_USER_ID


def log_track_play(db: Session, track: TrackRequest):
    user_id = get_or_create_dummy_user(db)
    media_id = upsert_media_metadata(db, track)

    log = PlayLog(user_id=user_id, media_id=media_id)
    db.add(log)
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
            "duration": media.duration
        }
        for log, media in logs
    ]

    return enrich_tracks_with_scores(db, raw_tracks)
