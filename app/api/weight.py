from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.db.session import get_db
from app.services.weight_service import apply_active_action, apply_passive_progress

router = APIRouter()

# Explicit schemas guarantee FastAPI will not throw 422 errors on standard JSON payloads


class ActionPayload(BaseModel):
    action: str


class PassivePayload(BaseModel):
    seconds: float


@router.post("/action/{external_id}")
async def track_action(external_id: str, payload: ActionPayload, db: Session = Depends(get_db)):
    if payload.action not in ["upvote", "downvote", "favorite", "trash"]:
        return {"status": "error", "message": "Invalid action"}

    new_score = apply_active_action(db, external_id, payload.action)
    return {"status": "success", "new_score": new_score}


@router.post("/passive/{external_id}")
async def passive_progress(external_id: str, payload: PassivePayload, db: Session = Depends(get_db)):
    new_score = apply_passive_progress(db, external_id, payload.seconds)
    return {"status": "success", "new_score": new_score}
