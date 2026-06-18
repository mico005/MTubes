import re
import asyncio
import httpx
from ytmusicapi import YTMusic

_ytmusic_client = YTMusic()


def clean_track_title(title: str) -> str:
    """Strips noise from YouTube titles to improve external database hit rates."""
    title = re.sub(
        r'(\(|\[).*?(official|video|lyric|audio|edit|remix).*?(\)|\])', '', title, flags=re.IGNORECASE)
    title = re.sub(r'(ft\.|feat\.).*', '', title, flags=re.IGNORECASE)
    return title.strip()


async def _fetch_from_lrclib(cleaned_title: str) -> str | None:
    """Fallback provider: Fast, async, but strict matching requirements."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"https://lrclib.net/api/search?q={cleaned_title}",
                timeout=5.0
            )
            response.raise_for_status()
            data = response.json()

            if data and isinstance(data, list) and data[0].get("plainLyrics"):
                return data[0]["plainLyrics"]
        except (httpx.RequestError, httpx.HTTPStatusError):
            return None
    return None


def _fetch_from_ytmusic_sync(title: str, video_id: str | None) -> str | None:
    """Primary provider: Uses exact video_id if available, otherwise falls back to a title search."""
    try:
        target_video_id = video_id

        if not target_video_id:
            results = _ytmusic_client.search(title, filter="songs", limit=1)
            if not results:
                return None
            target_video_id = results[0].get('videoId')

        if not target_video_id:
            return None

        watch_playlist = _ytmusic_client.get_watch_playlist(
            videoId=target_video_id)
        lyrics_id = watch_playlist.get("lyrics")

        if not lyrics_id:
            return None

        lyrics_data = _ytmusic_client.get_lyrics(lyrics_id)
        return lyrics_data.get("lyrics")
    except (KeyError, IndexError, ValueError, TypeError):
        return None


async def fetch_lyrics_from_provider(title: str, video_id: str | None = None) -> str | None:
    """
    Orchestrates lyric fetching.
    Attempts YTMusic first using the exact ID, falls back to LRCLIB text search if it fails.
    """
    cleaned_title = clean_track_title(title)

    ytmusic_lyrics = await asyncio.to_thread(_fetch_from_ytmusic_sync, cleaned_title, video_id)
    if ytmusic_lyrics:
        return ytmusic_lyrics

    return await _fetch_from_lrclib(cleaned_title)
