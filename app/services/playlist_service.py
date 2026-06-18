import uuid
from sqlalchemy.orm import Session
from app.db.models import Playlist, PlaylistTrack, MediaMetadata, WeightScore
from app.schemas import TrackRequest
from app.services.weight_service import enrich_tracks_with_scores
from app.services.common_service import get_or_create_dummy_user, upsert_media_metadata, DUMMY_USER_ID


def get_playlists(db: Session) -> list[dict]:
    playlists = db.query(Playlist).filter(
        Playlist.user_id == DUMMY_USER_ID).order_by(Playlist.created_at).all()
    return [{"id": str(p.id), "name": p.name} for p in playlists]


def create_playlist(db: Session, name: str) -> dict:
    user_id = get_or_create_dummy_user(db)
    playlist = Playlist(user_id=user_id, name=name)
    db.add(playlist)
    db.commit()
    return {"id": str(playlist.id), "name": playlist.name}


def add_track(db: Session, playlist_id: str, track: TrackRequest):
    media_id = upsert_media_metadata(db, track)
    valid_pid = uuid.UUID(playlist_id)

    exists = db.query(PlaylistTrack).filter_by(
        playlist_id=valid_pid, media_id=media_id).first()

    if not exists:
        ptrack = PlaylistTrack(playlist_id=valid_pid, media_id=media_id)
        db.add(ptrack)
        db.commit()


def remove_track(db: Session, playlist_id: str, external_id: str):
    media = db.query(MediaMetadata).filter_by(external_id=external_id).first()
    if not media:
        return
    db.query(PlaylistTrack).filter_by(playlist_id=uuid.UUID(
        playlist_id), media_id=media.id).delete()
    db.commit()


def _map_to_raw_tracks(media_results: list) -> list[dict]:
    """Helper to transform ORM models to raw track dicts."""
    return [{
        "id": media.external_id,
        "title": media.title,
        "uploader": media.uploader,
        "thumbnail": media.thumbnail,
        "duration": media.duration
    } for media in media_results]


def get_playlist_tracks(db: Session, playlist_id: str) -> list[dict]:
    results = (
        db.query(MediaMetadata)
        .join(PlaylistTrack, PlaylistTrack.media_id == MediaMetadata.id)
        .filter(PlaylistTrack.playlist_id == uuid.UUID(playlist_id))
        .order_by(PlaylistTrack.added_at.desc())
        .all()
    )
    raw_tracks = _map_to_raw_tracks(results)
    return enrich_tracks_with_scores(db, raw_tracks)


def get_favorite_tracks(db: Session) -> list[dict]:
    results = (
        db.query(MediaMetadata)
        .join(WeightScore, WeightScore.external_id == MediaMetadata.external_id)
        .filter(WeightScore.user_id == DUMMY_USER_ID, WeightScore.is_favorited == True)
        .order_by(WeightScore.updated_at.desc())
        .all()
    )
    raw_tracks = _map_to_raw_tracks(results)
    return enrich_tracks_with_scores(db, raw_tracks)
