import asyncio
import yt_dlp


async def get_direct_stream_url(video_id: str) -> str | None:
    """
    Extracts the direct Google video URL for the audio stream asynchronously.
    Offloads blocking I/O to a separate thread to protect the FastAPI event loop.
    """
    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
    }

    def extract():
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(
                    f"https://www.youtube.com/watch?v={video_id}", download=False)
                return info.get('url')
        except yt_dlp.utils.DownloadError:
            return None

    return await asyncio.to_thread(extract)
