from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.db.models import WeightScore, MediaMetadata
from app.services.common_service import get_or_create_dummy_user, DUMMY_USER_ID

DECAY_RATE_PER_DAY = 0.5


def _get_or_create_weight(db: Session, external_id: str) -> WeightScore:
    user_id = get_or_create_dummy_user(db)
    weight = db.query(WeightScore).filter(
        WeightScore.user_id == user_id,
        WeightScore.external_id == external_id
    ).first()

    if not weight:
        weight = WeightScore(
            user_id=user_id, external_id=external_id, base_score=0.0)
        db.add(weight)
        db.commit()
        db.refresh(weight)

    return weight


def calculate_effective_score(weight: WeightScore) -> float:
    if weight.is_trashed:
        return -1.0

    base = float(weight.base_score)

    if weight.last_played_at:
        days_since = (datetime.now(timezone.utc) -
                      weight.last_played_at.replace(tzinfo=timezone.utc)).days
        if days_since > 0:
            decay = days_since * DECAY_RATE_PER_DAY
            base = max(0.0, base - decay)

    if weight.is_favorited:
        base += 100.0

    return round(base, 2)


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


def enrich_tracks_with_scores(db: Session, tracks: list[dict]) -> list[dict]:
    user_id = get_or_create_dummy_user(db)
    external_ids = [t["id"] for t in tracks]

    weights = db.query(WeightScore).filter(
        WeightScore.user_id == user_id,
        WeightScore.external_id.in_(external_ids)
    ).all()

    score_map = {w.external_id: w for w in weights}

    enriched = []
    for track in tracks:
        w = score_map.get(track["id"])
        if w:
            track["score"] = calculate_effective_score(w)
            track["is_favorited"] = w.is_favorited
            track["is_trashed"] = w.is_trashed
        else:
            track["score"] = 0.0
            track["is_favorited"] = False
            track["is_trashed"] = False
        enriched.append(track)

    return enriched
