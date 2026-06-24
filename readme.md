# MTube

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-async-009688)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-ORM-red)
![yt-dlp](https://img.shields.io/badge/yt--dlp-extraction-orange)
![librosa](https://img.shields.io/badge/librosa-DSP-yellow)
![SQLite/Postgres](https://img.shields.io/badge/DB-SQLite%20%7C%20PostgreSQL-336791)
![License](https://img.shields.io/badge/license-unspecified-lightgrey)

## Overview

MTube is a FastAPI backend and Vanilla JS/Bootstrap frontend that replicates core YouTube Music functionality on top of `yt-dlp` and `ytmusicapi`. It proxies audio playback, tracks user engagement through an active/passive weighting system, and ranks recommendations using acoustic feature vectors extracted from played tracks via `librosa`.

## Core Features

- **Proxy Audio Streaming** — The `/api/stream/{video_id}` endpoint resolves a direct media URL via `yt-dlp` and re-streams it to the browser through a persistent `httpx.AsyncClient`, forwarding `Range` headers and `Accept-Ranges`/`Content-Range`/`Content-Length` response headers to support seeking, while bypassing the CORS and direct-linking restrictions YouTube enforces on its CDN URLs.

- **Acoustic Analysis & Recommendation** — When a track is played or surfaced as a recommendation candidate, a background task downloads the audio with `yt-dlp`, then extracts a feature vector with `librosa`:
  - **Energy** from mean RMS amplitude
  - **Danceability** from estimated tempo (BPM)
  - **Acousticness** as the inverse of energy
  - A zero-crossing-rate variance heuristic flags likely speech/podcast content (`is_valid_music`), auto-trashing non-music audio so it's excluded from rotation.

  A user's **session vector** is built by averaging the feature vectors of their last 5 played tracks. Recommendation candidates are ranked against this vector using **cosine similarity**, with a tunable random "drift factor" injected to avoid strict echo chambers (lower drift for familiar picks, higher drift for discovery mode).

- **Dynamic Weighting System** — Each track carries a `WeightScore` per user, combining:
  - **Active signals**: upvote (+1.0), downvote (−1.0, floored at 0), favorite (toggle, +100 bonus to effective score), and trash (hard −1.0 effective score, excluding the track from results).
  - **Passive signals**: listening duration is reported periodically and converted to score increments (`seconds / 10 * 0.1`).
  - **Time decay**: scores decay at a fixed rate per day since last play, so engagement naturally fades without continued listening.

  The `RecommendationWeightEngine` in `app/core/weight_system.py` is a stubbed-out interface for a future, more sophisticated affinity-graph algorithm; play events are already being logged to support it.

- **Redundant Lyrics Fetching** — Lyrics are resolved primarily through `ytmusicapi` (using the exact video ID's watch playlist when available, or a title search fallback), with an automatic fallback to the `lrclib.net` public API if no lyrics are found. Track titles are cleaned of noise tokens (`official`, `video`, `lyric`, `remix`, `feat.`, etc.) before any lookup to improve match rates.

- **Local DB with WAL Mode** — The default SQLite database is configured with `PRAGMA journal_mode=WAL` and `PRAGMA synchronous=NORMAL` on connect, allowing concurrent readers alongside a single writer — important given the app's mix of synchronous request handlers and background analysis tasks hitting the database simultaneously.

## Tech Stack

| Layer                    | Technology                                                                               |
| ------------------------ | ---------------------------------------------------------------------------------------- |
| Backend framework        | FastAPI, Uvicorn                                                                         |
| Media extraction         | yt-dlp, ytmusicapi                                                                       |
| Audio proxying           | httpx (`AsyncClient`, streaming)                                                         |
| DSP / feature extraction | librosa, NumPy                                                                           |
| Lyrics fallback          | lrclib.net (via httpx)                                                                   |
| ORM / persistence        | SQLAlchemy (SQLite by default, PostgreSQL via `psycopg2-binary` for production/Supabase) |
| Validation / config      | Pydantic, Pydantic Settings                                                              |
| Frontend                 | Vanilla JS, Bootstrap 5, Bootstrap Icons                                                 |

## System Architecture / How It Works

1. **Search** — `app/api/search.py` calls `yt_dlp`'s native `ytsearch` (flat extraction) for results, then enriches each candidate with the user's existing `WeightScore` before returning a ranked list.
2. **Playback** — The frontend requests `/api/stream/{video_id}`. The backend resolves a direct CDN URL via `yt_service.get_direct_stream_url` and streams the response chunk-by-chunk back to the browser, honoring `Range` requests for seeking and aborting cleanly on client disconnect.
3. **Play logging & analysis trigger** — A play is recorded via `POST /api/history/`, which upserts `MediaMetadata`, writes a `PlayLog` row, and — if the track has no extracted features yet — schedules `process_audio_features` as a `BackgroundTasks` job.
4. **Background feature extraction pipeline**:
   - `yt-dlp` downloads and transcodes the audio to a temp MP3 (via `run_in_executor` on the default thread pool, keeping the event loop unblocked).
   - The CPU-bound `librosa` extraction (`_extract_features_cpu_bound`) runs in a dedicated `ProcessPoolExecutor` (2 workers) to avoid blocking both the event loop and the I/O thread pool.
   - Resulting energy/danceability/acousticness values are written back to `MediaMetadata`, and temp files are cleaned up regardless of outcome.
   - Tracks classified as speech/noise are automatically trashed via the weighting system.
5. **Session graph & recommendations** — `recommendation_service.py` builds a session vector from the last 5 analyzed plays and ranks candidates (from `/recommendation/mix` or `/recommendation/related/{video_id}`) by cosine similarity to that vector, blended with random drift and the user's existing weight scores. Unanalyzed candidates encountered during this process are themselves queued for background feature extraction, so the feature store grows organically as the catalog is explored.
6. **Engagement feedback loop** — Upvotes, downvotes, favorites, trashes, and passive listening time all flow through `weight_service.py`, updating `WeightScore` rows that feed back into search ranking, the "Top" recommendation endpoint, and history/playlist views.

## Local Setup & Installation

### Requirements

- Python 3.10+
- `ffmpeg` installed and available on `PATH` (required by `yt-dlp`'s audio extraction postprocessor and by `librosa`)

### Steps

#### 1. Clone the repository

```bash
git clone <repository-url>
cd mtube
```

#### 2. Create and activate a virtual environment

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
```

# 3. Install dependencies

```bash
pip install -r requirements.txt
```

# 4. (Optional) Configure environment

Create a .env file to override settings, e.g. to point at PostgreSQL/Supabase:
DATABASE_URL=postgresql://user:password@host:port/dbname
By default, MTube uses a local SQLite file: music_clone.db

# 5. Run the development server

```bash
uvicorn app.main:app --reload
```

The app will be available at `http://127.0.0.1:8000`. Database tables are created automatically on startup via `Base.metadata.create_all`.

## Project Structure

```
├── app
│   ├── api/                  # FastAPI routers — one module per resource (search, stream, lyrics, history, weight, recommendation, playlist)
│   ├── core/
│   │   ├── config.py         # Pydantic Settings (project name, DATABASE_URL, debug flag)
│   │   └── weight_system.py  # Stubbed future affinity/weighting engine interface
│   ├── db/
│   │   ├── models.py         # SQLAlchemy models: User, MediaMetadata, PlayLog, WeightScore, Playlist, PlaylistTrack
│   │   └── session.py        # Engine setup, WAL pragma configuration, session dependency
│   ├── services/
│   │   ├── analysis_service.py       # yt-dlp download + librosa CPU-bound feature extraction pipeline
│   │   ├── common_service.py         # Shared helpers: dummy user bootstrap, media metadata upsert
│   │   ├── history_service.py        # Play logging and analysis scheduling
│   │   ├── lyrics_service.py         # ytmusicapi + lrclib lyrics resolution
│   │   ├── playlist_service.py       # Playlist CRUD and favorites
│   │   ├── recommendation_service.py # Session vector construction, cosine-similarity ranking, mix/related logic
│   │   ├── search_service.py         # yt-dlp-based search and autocomplete suggestions
│   │   ├── weight_service.py         # Active/passive scoring, decay, score enrichment
│   │   └── yt_service.py             # Direct stream URL resolution
│   ├── main.py                # FastAPI app instance, router registration, static/template mounting
│   └── schemas.py             # Pydantic request/response models (TrackRequest, TrackResponse)
├── static
│   ├── css/style.css          # Application styling
│   └── js/player.js           # Audio playback, queue, and UI control logic
├── templates
│   └── index.html             # Single-page app shell (Bootstrap-based player UI)
├── favicon.ico
└── requirements.txt
```
