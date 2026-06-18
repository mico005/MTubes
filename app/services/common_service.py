from sqlalchemy.orm import Session
from app.db.models import User, MediaMetadata
from app.schemas import TrackRequest
import uuid

DUMMY_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000000")


def get_or_create_dummy_user(db: Session) -> uuid.UUID:
    """Ensures the dummy user exists and returns their ID."""
    user = db.query(User).filter(User.id == DUMMY_USER_ID).first()
    if not user:
        user = User(id=DUMMY_USER_ID, username="anonymous_listener")
        db.add(user)
        db.commit()
    return user.id


def upsert_media_metadata(db: Session, track: TrackRequest) -> uuid.UUID:
    """Ensures media metadata exists and returns its internal UUID."""
    media = db.query(MediaMetadata).filter(
        MediaMetadata.external_id == track.id).first()
    if media:
        return media.id

    new_media = MediaMetadata(
        external_id=track.id,
        title=track.title,
        uploader=track.uploader,
        thumbnail=track.thumbnail,
        duration=track.duration
    )
    db.add(new_media)
    db.flush()
    return new_media.id
