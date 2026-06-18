from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import os

from app.api.search import router as search_router
from app.api.stream import router as stream_router
from app.api.lyrics import router as lyrics_router
from app.api.history import router as history_router
from app.api.weight import router as weight_router
from app.api.recommendation import router as rec_router
from app.api.playlist import router as playlist_router

from app.db.session import engine
from app.db.models import Base

Base.metadata.create_all(bind=engine)

app = FastAPI(title="YouTube Music Clone MVP")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"]
)

static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.include_router(search_router, prefix="/api/search", tags=["Search"])
app.include_router(stream_router, prefix="/api/stream", tags=["Stream"])
app.include_router(lyrics_router, prefix="/api/lyrics", tags=["Lyrics"])
app.include_router(history_router, prefix="/api/history", tags=["History"])
app.include_router(weight_router, prefix="/api/weight", tags=["Weight"])
app.include_router(rec_router, prefix="/api/recommendation",
                   tags=["Recommendation"])
app.include_router(playlist_router, prefix="/api/playlist", tags=["Playlist"])


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    template_path = os.path.join(os.path.dirname(
        __file__), "..", "templates", "index.html")
    with open(template_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())
