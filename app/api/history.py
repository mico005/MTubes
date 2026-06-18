from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas import TrackRequest
from app.services.history_service import log_track_play, fetch_recent_history

router = APIRouter()


@router.post("/")
async def record_play_history(
    track: TrackRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Logs the track play in the background to prevent blocking the audio stream response."""
    background_tasks.add_task(log_track_play, db, track)
    return {"status": "success", "message": "Play logged successfully"}


@router.get("/")
async def get_play_history(limit: int = 20, db: Session = Depends(get_db)):
    """Returns the user's play history."""
    history = fetch_recent_history(db, limit)
    return {"status": "success", "data": history}
