from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
import asyncio

from app.db.session import get_db
from app.services.search_service import execute_search, get_search_suggestions_sync
from app.services.weight_service import enrich_tracks_with_scores

router = APIRouter()


@router.get("/")
async def search_media(query: str, limit: int = 100, db: Session = Depends(get_db)):
    """Executes search and returns user-weighted results."""
    if not query:
        raise HTTPException(
            status_code=400, detail="Query parameter is required")

    raw_results = await execute_search(query, limit)

    final_results = enrich_tracks_with_scores(db, raw_results)
    final_results.sort(key=lambda x: x.get("score", 0.0), reverse=True)

    return {"status": "success", "data": final_results}


@router.get("/suggestions")
async def search_suggestions(q: str):
    """Offloads the external suggestion fetch to prevent event loop blocking."""
    suggestions = await asyncio.to_thread(get_search_suggestions_sync, q)
    return {"status": "success", "data": suggestions}
