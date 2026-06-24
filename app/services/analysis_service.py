import asyncio
import os
import tempfile
import uuid
import glob
from concurrent.futures import ProcessPoolExecutor
from typing import Dict, Any

import librosa
import numpy as np
import yt_dlp
from sqlalchemy.orm import Session

from app.db.models import MediaMetadata
from app.services.weight_service import apply_active_action

cpu_pool = ProcessPoolExecutor(max_workers=2)


def _download_audio_to_temp(video_id: str, base_path: str) -> bool:
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f"{base_path}.%(ext)s",
        'quiet': True,
        'no_warnings': True,
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}],
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(
                f"https://www.youtube.com/watch?v={video_id}", download=True)
        return True
    except Exception as e:
        print(f"[DSP Error] yt-dlp download failed for {video_id}: {e}")
        return False


def _extract_features_cpu_bound(audio_path: str) -> Dict[str, Any]:
    try:
        y, sr = librosa.load(audio_path, sr=22050, mono=True, duration=60)

        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        rms_energy = librosa.feature.rms(y=y)
        zcr = librosa.feature.zero_crossing_rate(y=y)

        energy = min(1.0, float(np.mean(rms_energy)) / 0.5)
        bpm = float(tempo[0] if isinstance(tempo, np.ndarray) else tempo)
        danceability = min(1.0, bpm / 200.0)

        # Layer 2: Acoustic Speech/Noise Validation
        # High ZCR variance is indicative of spoken word (consonants/fricatives)
        zcr_var = float(np.var(zcr))
        is_speech_or_noise = (zcr_var > 0.04 and danceability < 0.35)

        return {
            "energy": round(energy, 3),
            "danceability": round(danceability, 3),
            "acousticness": round(1.0 - energy, 3),
            "is_valid_music": not is_speech_or_noise
        }
    except Exception as e:
        print(f"[DSP Error] librosa extraction failed for {audio_path}: {e}")
        return {}


async def process_audio_features(db: Session, video_id: str, internal_id: Any):
    db_media = db.query(MediaMetadata).filter(
        MediaMetadata.id == internal_id).first()
    if not db_media or getattr(db_media, 'features_extracted', False):
        db.rollback()
        return

    db.rollback()

    random_id = str(uuid.uuid4())
    base_path = os.path.join(tempfile.gettempdir(),
                             f"mtube_analysis_{random_id}")
    mp3_path = f"{base_path}.mp3"

    try:
        loop = asyncio.get_running_loop()

        success = await loop.run_in_executor(None, _download_audio_to_temp, video_id, base_path)
        if not success or not os.path.exists(mp3_path):
            print(
                f"[DSP Error] Missing MP3 file after download for {video_id}")
            return

        features = await loop.run_in_executor(cpu_pool, _extract_features_cpu_bound, mp3_path)
        if not features:
            print(f"[DSP Error] Feature array empty for {video_id}")
            return

        # If acoustic analysis proves this is a podcast/interview, auto-trash it.
        if not features.get("is_valid_music", True):
            print(
                f"[DSP Action] Auto-trashing non-music audio track: {video_id}")
            apply_active_action(db, video_id, "trash")

        db_media = db.query(MediaMetadata).filter(
            MediaMetadata.id == internal_id).first()
        if db_media:
            db_media.energy = features["energy"]
            db_media.danceability = features["danceability"]
            db_media.acousticness = features["acousticness"]
            db_media.features_extracted = True
            db.commit()
            print(f"[DSP Success] Vectors extracted and saved for {video_id}")

    except Exception as e:
        print(f"[DSP Error] Pipeline crashed for {video_id}: {e}")
    finally:
        for temp_file in glob.glob(f"{base_path}*"):
            try:
                os.remove(temp_file)
            except OSError:
                pass
