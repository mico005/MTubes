from sqlalchemy.orm import Session
from datetime import datetime, timezone
from app.db.models import WeightScore
from app.services.common_service import get_or_create_dummy_user

DECAY_RATE_PER_DAY = 0.5


def _get_or_create_weight(db: Session, external_id: str) -> WeightScore:
    user_id = get_or_create_dummy_user(db)
    weight = db.query(WeightScore).filter_by(
        user_id=user_id, external_id=external_id).first()

    if not weight:
        weight = WeightScore(user_id=user_id, external_id=external_id)
        db.add(weight)
        db.commit()
        db.refresh(weight)

    return weight


def calculate_effective_score(weight: WeightScore | None) -> float:
    if not weight:
        return 0.0
    if weight.is_trashed:
        return -1.0

    base = float(weight.base_score)
    if weight.is_favorited:
        base += 10.0

    if weight.last_played_at:
        lp = weight.last_played_at
        if isinstance(lp, str):
            try:
                lp = datetime.fromisoformat(lp)
            except ValueError:
                pass

        if isinstance(lp, datetime):
            if lp.tzinfo is None:
                lp = lp.replace(tzinfo=timezone.utc)
            days_inactive = (datetime.now(timezone.utc) - lp).days
            if days_inactive > 0:
                base = max(0.0, base - (days_inactive * DECAY_RATE_PER_DAY))

    return round(base, 1)


def apply_active_action(db: Session, external_id: str, action: str) -> float:
    weight = _get_or_create_weight(db, external_id)

    if action == "upvote":
        weight.base_score = float(weight.base_score) + 1.0
    elif action == "downvote":
        weight.base_score = max(0.0, float(weight.base_score) - 1.0)
    elif action == "favorite":
        weight.is_favorited = not weight.is_favorited
    elif action == "trash":
        weight.is_trashed = True

    db.commit()
    db.refresh(weight)
    return calculate_effective_score(weight)


def apply_passive_progress(db: Session, external_id: str, seconds_listened: float) -> float:
    if seconds_listened <= 0:
        return 0.0

    weight = _get_or_create_weight(db, external_id)
    if weight.is_trashed:
        return -1.0

    increment = (seconds_listened / 10.0) * 0.1
    weight.base_score = float(weight.base_score) + increment
    weight.last_played_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(weight)
    return calculate_effective_score(weight)


def get_scores_for_tracks(db: Session, track_ids: list[str]) -> dict[str, dict]:
    user_id = get_or_create_dummy_user(db)
    weights = db.query(WeightScore).filter(
        WeightScore.user_id == user_id,
        WeightScore.external_id.in_(track_ids)
    ).all()

    return {
        w.external_id: {
            "score": calculate_effective_score(w),
            "is_favorited": w.is_favorited,
            "is_trashed": w.is_trashed
        } for w in weights
    }


def enrich_tracks_with_scores(db: Session, raw_tracks: list[dict]) -> list[dict]:
    """Centralized logic to apply user affinity scores and strictly filter out trashed items."""
    track_ids = [t["id"] for t in raw_tracks]
    score_map = get_scores_for_tracks(db, track_ids)

    final_tracks = []
    for track in raw_tracks:
        metrics = score_map.get(
            track["id"], {"score": 0.0, "is_favorited": False, "is_trashed": False})

        if metrics["is_trashed"]:
            continue

        track.update(metrics)
        final_tracks.append(track)

    return final_tracks
