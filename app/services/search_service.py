import asyncio
import yt_dlp


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
                    "thumbnail": entry.get("thumbnails", [{}])[0].get("url", "")
                }
                for entry in result['entries']
            ]

    return await asyncio.to_thread(fetch)
