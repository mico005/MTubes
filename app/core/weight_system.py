from sqlalchemy.orm import Session
from app.db.models import PlayLog, WeightScore
import uuid


class RecommendationWeightEngine:
    """
    Interface for the future custom weight system algorithm.
    Currently stubbed out to ensure architecture is ready for Day 1 data collection.
    """

    def __init__(self, db_session: Session):
        self.db = db_session

    def log_play_event(self, user_id: uuid.UUID, media_id: uuid.UUID, duration: float):
        """Logs user interaction. Call this asynchronously via background tasks."""
        log = PlayLog(user_id=user_id, media_id=media_id,
                      play_duration_seconds=duration)
        self.db.add(log)
        self.db.commit()

    def calculate_affinity(self, user_id: uuid.UUID):
        """
        Stub: Will recalculate the user's affinity graph based on PlayLogs.
        Should run periodically as a cron job or async worker.
        """
        pass
