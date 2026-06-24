import asyncio
import yt_dlp
from ytmusicapi import YTMusic

_ytmusic_client = YTMusic()


async def execute_search(query: str, max_results: int = 10) -> list[dict]:
    """
    Searches YouTube. Uses yt-dlp native ytsearch to avoid relying on fragile
    third-party scraper packages. Guaranteed to stay updated with yt-dlp core.
    """
    ydl_opts = {
        'format': 'bestaudio/best',
        'extract_flat': True,
        'quiet': True,
        'no_warnings': True,
    }

    def fetch():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(
                f"ytsearch{max_results}:{query}", download=False)
            if 'entries' not in result:
                return []

            return [
                {
                    "id": entry.get("id"),
                    "title": entry.get("title"),
                    "duration": entry.get("duration"),
                    "uploader": entry.get("uploader"),
                    "thumbnail": entry.get("thumbnails", [{}])[0].get("url", "") if entry.get("thumbnails") else ""
                }
                for entry in result['entries']
            ]

    return await asyncio.to_thread(fetch)


def get_search_suggestions_sync(query: str) -> list[str]:
    """Fetches live autocomplete suggestions from YouTube Music."""
    if not query.strip():
        return []
    try:
        raw_suggestions = _ytmusic_client.get_search_suggestions(query)
        return [
            item.get("query", "") if isinstance(item, dict) else str(item)
            for item in raw_suggestions
        ]
    except Exception as e:
        print(f"[Search Error] Failed to fetch suggestions for '{query}': {e}")
        return []
