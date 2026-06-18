from fastapi import APIRouter, HTTPException
from app.services.lyrics_service import fetch_lyrics_from_provider

router = APIRouter()


@router.get("/")
async def get_lyrics(title: str):
    """Endpoint to fetch cleaned lyrics based on a track title."""
    if not title:
        raise HTTPException(
            status_code=400, detail="Title parameter is required")

    lyrics = await fetch_lyrics_from_provider(title)

    if not lyrics:
        raise HTTPException(status_code=404, detail="Lyrics not found")

    return {"status": "success", "data": lyrics}
