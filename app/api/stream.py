from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
import httpx
from app.services.yt_service import get_direct_stream_url

router = APIRouter()

# Use a single persistent client for all stream requests
# This enables connection pooling and prevents overhead
stream_client = httpx.AsyncClient(
    timeout=10.0,
    headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
)


@router.get("/{video_id}")
async def proxy_audio_stream(video_id: str, request: Request):
    stream_url = await get_direct_stream_url(video_id)
    if not stream_url:
        raise HTTPException(status_code=404, detail="Audio stream not found")

    range_header = request.headers.get("Range")
    headers = {"Range": range_header} if range_header else {}

    # Stream the response from YouTube
    try:
        resp = await stream_client.get(stream_url, headers=headers, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=502, detail=f"Streaming service unreachable: {str(e)}")

    def get_forwarded_headers(response):
        return {k: v for k, v in response.headers.items()
                if k.lower() in ["accept-ranges", "content-range", "content-length", "content-type"]}

    async def stream_generator():
        # Using stream=True directly in the client call is safer
        async with stream_client.stream("GET", stream_url, headers=headers) as r:
            async for chunk in r.aiter_bytes(chunk_size=16384):
                yield chunk

    return StreamingResponse(
        stream_generator(),
        status_code=206 if range_header else 200,
        headers=get_forwarded_headers(resp)
    )
