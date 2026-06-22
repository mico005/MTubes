import uuid
from sqlalchemy.orm import Session
from app.db.models import Playlist, PlaylistTrack, MediaMetadata
from app.schemas import TrackRequest
from app.services.weight_service import enrich_tracks_with_scores
from app.services.common_service import get_or_create_dummy_user, upsert_media_metadata, DUMMY_USER_ID


def get_playlists(db: Session) -> list[dict]:
    user_id = get_or_create_dummy_user(db)
    playlists = db.query(Playlist).filter(Playlist.user_id == user_id).all()
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


def get_playlist_tracks(db: Session, playlist_id: str) -> list[dict]:
    valid_pid = uuid.UUID(playlist_id)

    results = (
        db.query(MediaMetadata)
        .join(PlaylistTrack, PlaylistTrack.media_id == MediaMetadata.id)
        .filter(PlaylistTrack.playlist_id == valid_pid)
        .all()
    )

    raw_tracks = [
        {
            "id": m.external_id,
            "title": m.title,
            "uploader": m.uploader,
            "thumbnail": m.thumbnail,
            "duration": m.duration,
        }
        for m in results
    ]

    return enrich_tracks_with_scores(db, raw_tracks)


def get_favorites(db: Session) -> list[dict]:
    user_id = get_or_create_dummy_user(db)
    from app.db.models import WeightScore
    results = (
        db.query(MediaMetadata)
        .join(WeightScore, WeightScore.external_id == MediaMetadata.external_id)
        .filter(WeightScore.user_id == user_id, WeightScore.is_favorited == True, WeightScore.is_trashed == False)
        .all()
    )

    raw_tracks = [
        {
            "id": m.external_id,
            "title": m.title,
            "uploader": m.uploader,
            "thumbnail": m.thumbnail,
            "duration": m.duration,
        }
        for m in results
    ]

    return enrich_tracks_with_scores(db, raw_tracks)


def get_favorite_tracks(db: Session) -> list[dict]:
    user_id = get_or_create_dummy_user(db)
    from app.db.models import WeightScore
    results = (
        db.query(MediaMetadata)
        .join(WeightScore, WeightScore.external_id == MediaMetadata.external_id)
        .filter(WeightScore.user_id == user_id, WeightScore.is_favorited == True, WeightScore.is_trashed == False)
        .all()
    )

    raw_tracks = [
        {
            "id": m.external_id,
            "title": m.title,
            "uploader": m.uploader,
            "thumbnail": m.thumbnail,
            "duration": m.duration,
        }
        for m in results
    ]

    return enrich_tracks_with_scores(db, raw_tracks)
