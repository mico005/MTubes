from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.recommendation_service import get_top_scored_local_tracks, get_weighted_related_tracks, get_history_mix

router = APIRouter()


@router.get("/top")
async def get_top_tracks(limit: int = 20, db: Session = Depends(get_db)):
    """Exploitation: Returns highest scored tracks from local history."""
    tracks = get_top_scored_local_tracks(db, limit)
    return {"status": "success", "data": tracks}


@router.get("/mix")
async def get_shuffled_mix(limit: int = 20, db: Session = Depends(get_db)):
    """Hybrid: Returns a discovery mix seeded by user history."""
    tracks = await get_history_mix(db, limit)
    return {"status": "success", "data": tracks}


@router.get("/related/{video_id}")
async def get_related_tracks(video_id: str, mode: str = "all", db: Session = Depends(get_db)):
    """Exploration: Returns external tracks weighted and filtered by queue mode."""
    tracks = await get_weighted_related_tracks(db, video_id, mode)
    return {"status": "success", "data": tracks}
