from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas import TrackRequest
from app.services.history_service import log_track_play_with_analysis, fetch_recent_history

router = APIRouter()

# Removed 'async' so FastAPI automatically handles synchronous DB calls in a threadpool


@router.post("/")
def record_play_history(
    track: TrackRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    log_track_play_with_analysis(db, track, background_tasks)
    return {"status": "success", "message": "Play logged successfully"}


@router.get("/")
def get_play_history(limit: int = 20, db: Session = Depends(get_db)):
    history = fetch_recent_history(db, limit)
    return {"status": "success", "data": history}
