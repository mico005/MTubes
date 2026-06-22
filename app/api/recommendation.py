from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.recommendation_service import (
    get_top_scored_local_tracks,
    get_weighted_related_tracks,
    get_history_mix,
)

router = APIRouter()


@router.get("/top")
async def get_top_tracks(limit: int = 20, db: Session = Depends(get_db)):
    tracks = get_top_scored_local_tracks(db, limit)
    return {"status": "success", "data": tracks}


@router.get("/mix")
async def get_shuffled_mix(
    limit: int = 100,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
    tracks = await get_history_mix(db, limit, background_tasks)
    return {"status": "success", "data": tracks}


@router.get("/related/{video_id}")
async def get_related_tracks(
    video_id: str,
    mode: str = "all",
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
):
    tracks = await get_weighted_related_tracks(db, video_id, mode, background_tasks)
    return {"status": "success", "data": tracks}
