import random
import asyncio

import numpy as np
import requests
from fastapi import BackgroundTasks
from sqlalchemy.orm import Session
from ytmusicapi import YTMusic

from app.db.models import WeightScore, MediaMetadata, PlayLog
from app.services.weight_service import enrich_tracks_with_scores, calculate_effective_score
from app.services.common_service import DUMMY_USER_ID
from app.services.analysis_service import process_audio_features
from app.db.session import SessionLocal

_ytmusic_client = YTMusic()
SESSION_VECTOR_TRACK_WINDOW = 5


def get_top_scored_local_tracks(db: Session, limit: int = 20) -> list[dict]:
    weights = db.query(WeightScore, MediaMetadata).join(
        MediaMetadata, WeightScore.external_id == MediaMetadata.external_id
    ).filter(
        WeightScore.user_id == DUMMY_USER_ID,
        WeightScore.is_trashed == False
    ).all()

    scored_tracks = []
    for weight, media in weights:
        score = calculate_effective_score(weight)
        if score <= 0:
            continue
        scored_tracks.append({
            "id": media.external_id,
            "title": media.title,
            "uploader": media.uploader,
            "thumbnail": media.thumbnail,
            "duration": media.duration,
            "score": score,
            "is_favorited": weight.is_favorited,
            "is_trashed": False,
        })

    scored_tracks.sort(key=lambda x: x["score"], reverse=True)
    return scored_tracks[:limit]


def _parse_yt_duration(duration_str: str | None) -> int:
    if not duration_str:
        return 0
    parts = duration_str.split(":")
    return sum(int(x) * 60 ** i for i, x in enumerate(reversed(parts)))


def _fetch_ytmusic_related(video_id: str) -> list[dict]:
    try:
        watch_playlist = _ytmusic_client.get_watch_playlist(
            videoId=video_id, limit=15
        )
        raw_tracks = watch_playlist.get("tracks", [])

        parsed_tracks = []
        for track in raw_tracks[1:]:
            if not track.get("videoId"):
                continue
            artist_names = ", ".join(
                [a.get("name", "") for a in track.get("artists", [])]
            )
            available_thumbnails = track.get("thumbnail", [])
            highest_res_thumbnail = available_thumbnails[-1]["url"] if available_thumbnails else ""
            parsed_tracks.append({
                "id": track["videoId"],
                "title": track.get("title", "Unknown Title"),
                "uploader": artist_names,
                "thumbnail": highest_res_thumbnail,
                "duration": _parse_yt_duration(track.get("length")),
            })
        return parsed_tracks
    except Exception:
        return []


def _build_session_vector(db: Session) -> np.ndarray | None:
    recently_played_logs = (
        db.query(PlayLog, MediaMetadata)
        .join(MediaMetadata, PlayLog.media_id == MediaMetadata.id)
        .filter(
            PlayLog.user_id == DUMMY_USER_ID,
            MediaMetadata.features_extracted == True,
        )
        .order_by(PlayLog.played_at.desc())
        .limit(SESSION_VECTOR_TRACK_WINDOW)
        .all()
    )

    if not recently_played_logs:
        return None

    feature_vectors = [
        np.array([media.energy, media.danceability, media.acousticness])
        for _, media in recently_played_logs
    ]
    return np.mean(feature_vectors, axis=0)


def _compute_cosine_similarity(vector_a: np.ndarray, vector_b: np.ndarray) -> float:
    magnitude_a = np.linalg.norm(vector_a)
    magnitude_b = np.linalg.norm(vector_b)

    if magnitude_a == 0.0 or magnitude_b == 0.0:
        return 0.0

    return float(np.dot(vector_a, vector_b) / (magnitude_a * magnitude_b))


def _run_extraction_sync_wrapper(video_id: str, internal_id):
    bg_db = SessionLocal()
    try:
        asyncio.run(process_audio_features(bg_db, video_id, internal_id))
    finally:
        bg_db.close()


def _schedule_feature_extraction_for_unanalyzed_tracks(
    unanalyzed_tracks_data: list[dict],
    background_tasks: BackgroundTasks,
):
    for track_data in unanalyzed_tracks_data:
        background_tasks.add_task(
            _run_extraction_sync_wrapper, track_data["external_id"], track_data["internal_id"]
        )


def _ensure_media_records_exist(db: Session, candidate_tracks: list[dict]) -> dict:
    from app.services.common_service import upsert_media_metadata
    from app.schemas import TrackRequest

    id_map = {}
    for track in candidate_tracks:
        media_id = upsert_media_metadata(db, TrackRequest(**track))
        # Keep media_id strictly as a UUID. Do not cast it to a string.
        id_map[track["id"]] = media_id
    return id_map


def _rank_candidates_by_session_vector(
    db: Session,
    candidate_tracks: list[dict],
    session_vector: np.ndarray,
    drift_factor: float = 0.08
) -> list[dict]:
    analyzed_media_records = (
        db.query(MediaMetadata)
        .filter(
            MediaMetadata.external_id.in_([t["id"] for t in candidate_tracks]),
            MediaMetadata.features_extracted == True,
        )
        .all()
    )

    feature_map = {
        media.external_id: np.array(
            [media.energy, media.danceability, media.acousticness])
        for media in analyzed_media_records
    }

    ranked_tracks = []
    for track in candidate_tracks:
        candidate_vector = feature_map.get(track["id"])
        if candidate_vector is None:
            ranked_tracks.append({**track, "similarity": 0.65})
            continue

        similarity_score = _compute_cosine_similarity(
            session_vector, candidate_vector)
        ranked_tracks.append({**track, "similarity": similarity_score})

    # Inject noise to allow organic mood gradations instead of strict echo chambers
    for track in ranked_tracks:
        noise = random.uniform(-drift_factor, drift_factor)
        track["effective_rank"] = track.get("similarity", 0.0) + noise

    ranked_tracks.sort(key=lambda x: x["effective_rank"], reverse=True)
    return ranked_tracks


async def get_history_mix(
    db: Session,
    limit: int = 100,
    background_tasks: BackgroundTasks | None = None
) -> list[dict]:
    top_tracks = get_top_scored_local_tracks(db, limit=50)
    if not top_tracks:
        return []

    seed_track = random.choice(top_tracks)
    related_results = await asyncio.to_thread(_fetch_ytmusic_related, seed_track["id"])

    raw_mix = top_tracks[:5] + (related_results or [])
    unique_mix = list({t["id"]: t for t in raw_mix}.values())

    if background_tasks is not None:
        id_map = _ensure_media_records_exist(db, unique_mix)
        analyzed_ids = {
            m.external_id for m in db.query(MediaMetadata.external_id)
            .filter(
                MediaMetadata.external_id.in_([t["id"] for t in unique_mix]),
                MediaMetadata.features_extracted == True
            ).all()
        }

        unanalyzed_tracks_data = [
            {"external_id": t["id"], "internal_id": id_map[t["id"]]}
            for t in unique_mix if t["id"] not in analyzed_ids
        ]
        _schedule_feature_extraction_for_unanalyzed_tracks(
            unanalyzed_tracks_data, background_tasks)

    session_vector = _build_session_vector(db)
    if session_vector is not None:
        ranked_mix = _rank_candidates_by_session_vector(
            db, unique_mix, session_vector, drift_factor=0.15)
        if ranked_mix:
            return enrich_tracks_with_scores(db, ranked_mix[:limit])

    weighted_mix = enrich_tracks_with_scores(db, unique_mix)
    random.shuffle(weighted_mix)
    return weighted_mix[:limit]


async def get_weighted_related_tracks(
    db: Session,
    video_id: str,
    mode: str = "all",
    background_tasks: BackgroundTasks | None = None,
) -> list[dict]:
    external_candidate_tracks = await asyncio.to_thread(_fetch_ytmusic_related, video_id)
    if not external_candidate_tracks:
        return []

    id_map = _ensure_media_records_exist(db, external_candidate_tracks)

    if background_tasks is not None:
        analyzed_external_ids = {
            media.external_id
            for media in db.query(MediaMetadata.external_id)
            .filter(
                MediaMetadata.external_id.in_(
                    [t["id"] for t in external_candidate_tracks]
                ),
                MediaMetadata.features_extracted == True,
            )
            .all()
        }
        unanalyzed_tracks_data = [
            {"external_id": t["id"], "internal_id": id_map[t["id"]]}
            for t in external_candidate_tracks
            if t["id"] not in analyzed_external_ids
        ]
        _schedule_feature_extraction_for_unanalyzed_tracks(
            unanalyzed_tracks_data, background_tasks
        )

    # 1. Apply baseline user scores first
    scored_candidates = enrich_tracks_with_scores(
        db, external_candidate_tracks)

    # 2. Filter based on UI Mode BEFORE ranking
    filtered_candidates = []
    for track in scored_candidates:
        if mode == "familiar" and track.get("score", 0.0) <= 0.0:
            continue
        if mode == "discover" and track.get("score", 0.0) >= 1.0:
            continue
        filtered_candidates.append(track)

    if not filtered_candidates:
        return []

    # 3. Apply Acoustic Sorting to the filtered list
    session_vector = _build_session_vector(db)
    if session_vector is not None:
        # Discover mode uses higher drift to explore adjacent acoustic spaces faster
        drift = 0.25 if mode == "discover" else 0.08
        return _rank_candidates_by_session_vector(db, filtered_candidates, session_vector, drift)

    # 4. Fallback if no session vector exists yet
    if mode in ["familiar", "all"]:
        filtered_candidates.sort(
            key=lambda x: x.get("score", 0.0), reverse=True)
    elif mode == "discover":
        random.shuffle(filtered_candidates)

    return filtered_candidates
