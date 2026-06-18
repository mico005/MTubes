from sqlalchemy.orm import Session
from app.db.models import WeightScore, MediaMetadata
from app.services.weight_service import enrich_tracks_with_scores, calculate_effective_score
from app.services.common_service import DUMMY_USER_ID
from ytmusicapi import YTMusic
import asyncio
import random
import requests

_ytmusic_client = YTMusic()


def get_top_scored_local_tracks(db: Session, limit: int = 20) -> list[dict]:
    """Retrieves the highest scored tracks directly from local history."""
    weights = db.query(WeightScore, MediaMetadata).join(
        MediaMetadata, WeightScore.external_id == MediaMetadata.external_id
    ).filter(
        WeightScore.user_id == DUMMY_USER_ID,
        WeightScore.is_trashed == False
    ).all()

    results = []
    for weight, media in weights:
        score = calculate_effective_score(weight)
        if score > 0:
            results.append({
                "id": media.external_id,
                "title": media.title,
                "uploader": media.uploader,
                "thumbnail": media.thumbnail,
                "duration": media.duration,
                "score": score,
                "is_favorited": weight.is_favorited,
                "is_trashed": False
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]


def _parse_yt_duration(duration_str: str | None) -> int:
    """Converts formatted time strings to seconds."""
    if not duration_str:
        return 0
    parts = duration_str.split(':')
    return sum(int(x) * 60 ** i for i, x in enumerate(reversed(parts)))


def _fetch_ytmusic_related(video_id: str) -> list[dict]:
    """Synchronously queries YTMusic for algorithmic relations."""
    try:
        playlist = _ytmusic_client.get_watch_playlist(
            videoId=video_id, limit=15)
        raw_tracks = playlist.get("tracks", [])

        parsed_tracks = []
        for track in raw_tracks[1:]:
            if not track.get("videoId"):
                continue

            artists = ", ".join([a.get("name", "")
                                for a in track.get("artists", [])])
            thumbnails = track.get("thumbnail", [])
            thumb_url = thumbnails[-1]["url"] if thumbnails else ""

            parsed_tracks.append({
                "id": track["videoId"],
                "title": track.get("title", "Unknown Title"),
                "uploader": artists,
                "thumbnail": thumb_url,
                "duration": _parse_yt_duration(track.get("length"))
            })
        return parsed_tracks
    except (KeyError, IndexError, TypeError, ValueError, requests.exceptions.RequestException):
        return []


async def get_history_mix(db: Session, limit: int = 20) -> list[dict]:
    """Creates a true hybrid mix seeding from top local tracks and pulling algorithmic relations."""
    top_tracks = get_top_scored_local_tracks(db, limit=50)
    if not top_tracks:
        return []

    seed_tracks = random.sample(top_tracks, min(2, len(top_tracks)))

    related_results = []
    for seed in seed_tracks:
        result = await asyncio.to_thread(_fetch_ytmusic_related, seed["id"])
        if result:
            related_results.append(result)
        await asyncio.sleep(0.5)

    raw_mix = top_tracks[:5]
    for batch in related_results:
        raw_mix.extend(batch)

    unique_mix = {t["id"]: t for t in raw_mix}.values()
    weighted_mix = enrich_tracks_with_scores(db, list(unique_mix))
    random.shuffle(weighted_mix)

    return weighted_mix[:limit]


async def get_weighted_related_tracks(db: Session, video_id: str, mode: str = "all") -> list[dict]:
    """Fetches external tracks and filters them against local DB scores based on the active queue mode."""
    external_tracks = await asyncio.to_thread(_fetch_ytmusic_related, video_id)
    if not external_tracks:
        return []

    weighted_tracks = enrich_tracks_with_scores(db, external_tracks)
    final_results = []

    for track in weighted_tracks:
        if mode == "familiar" and track.get("score", 0.0) <= 0.0:
            continue
        if mode == "discover" and track.get("score", 0.0) >= 1.0:
            continue
        final_results.append(track)

    if mode in ["familiar", "all"]:
        final_results.sort(key=lambda x: x.get("score", 0.0), reverse=True)
    elif mode == "discover":
        random.shuffle(final_results)

    return final_results
