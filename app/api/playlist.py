from fastapi import APIRouter, Depends, Body, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.schemas import TrackRequest
from app.services.playlist_service import (
    get_playlists, create_playlist, add_track, remove_track,
    get_playlist_tracks, get_favorite_tracks
)

router = APIRouter()


@router.get("/")
def list_playlists(db: Session = Depends(get_db)):
    return {"status": "success", "data": get_playlists(db)}


@router.post("/")
def make_playlist(name: str = Body(..., embed=True), db: Session = Depends(get_db)):
    if not name or not name.strip():
        raise HTTPException(400, "Name required")
    return {"status": "success", "data": create_playlist(db, name.strip())}


@router.get("/favorites")
def list_favorites(db: Session = Depends(get_db)):
    return {"status": "success", "data": get_favorite_tracks(db)}


@router.get("/{playlist_id}/tracks")
def list_tracks(playlist_id: str, db: Session = Depends(get_db)):
    return {"status": "success", "data": get_playlist_tracks(db, playlist_id)}


@router.post("/{playlist_id}/tracks")
def add_playlist_track(playlist_id: str, track: TrackRequest, db: Session = Depends(get_db)):
    add_track(db, playlist_id, track)
    return {"status": "success"}


@router.delete("/{playlist_id}/tracks/{external_id}")
def delete_playlist_track(playlist_id: str, external_id: str, db: Session = Depends(get_db)):
    remove_track(db, playlist_id, external_id)
    return {"status": "success"}
