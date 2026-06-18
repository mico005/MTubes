from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.services.search_service import execute_search
from app.services.weight_service import enrich_tracks_with_scores

router = APIRouter()


@router.get("/")
async def search_media(query: str, limit: int = 100, db: Session = Depends(get_db)):
    """Executes search and returns user-weighted results."""
    if not query:
        raise HTTPException(
            status_code=400, detail="Query parameter is required")

    raw_results = await execute_search(query, limit)

    # Leverages the centralized enrichment logic to remove duplication
    final_results = enrich_tracks_with_scores(db, raw_results)

    # Python's sort is stable; items with identical scores (e.g., 0.0)
    # will preserve their original YouTube search relevance order.
    final_results.sort(key=lambda x: x.get("score", 0.0), reverse=True)

    return {"status": "success", "data": final_results}
