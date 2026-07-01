"""The 30/5 Feedback Engine — Phase 1 scope only: tracks active session
time and manages the 5-question check-in flow described in the blueprint.
The lie-detection classifier is explicitly Phase 3 in the blueprint's own
build plan and is not implemented here.

Known Phase 1 limitation: activity tracking below is in-process memory,
not persisted. That's fine for a single-instance MVP but won't survive a
restart or work correctly if this service scales to multiple instances —
swap _sessions for a Redis/Postgres-backed store before that happens; the
public function signatures here wouldn't need to change.
"""

import time
from dataclasses import dataclass
from typing import Dict, Optional

from semantic_wall.config import settings
from semantic_wall.db.supabase_client import get_client, is_configured
from semantic_wall.memory.store import mark_session_outcome

# A gap longer than this between chat turns isn't counted as active usage.
_MAX_ACTIVE_GAP_SECONDS = 5 * 60

CHECKIN_QUESTIONS = [
    {"id": "completion_confirmation", "text": "Did the agent complete the task you assigned?", "type": "bool"},
    {"id": "quality_rating", "text": "How would you rate the output delivered?", "type": "rating_1_5"},
    {"id": "improvement_note", "text": "What would have made that output better?", "type": "text_min_10_chars"},
    {"id": "used_in_real_work", "text": "Did you use that output in actual work?", "type": "bool"},
    {"id": "willingness_to_pay", "text": "Would you pay for this specific capability?", "type": "yes_no_maybe"},
]


class CheckinValidationError(ValueError):
    """Raised when a submitted check-in fails basic shape validation."""


@dataclass
class _SessionActivity:
    active_seconds: float = 0.0
    last_seen: Optional[float] = None
    checkin_due: bool = False
    last_checkin_at_seconds: float = 0.0


_sessions: Dict[str, _SessionActivity] = {}


def record_activity(session_id: str) -> None:
    """Call once per chat turn to accumulate active-usage time for a session."""
    now = time.monotonic()
    activity = _sessions.setdefault(session_id, _SessionActivity())

    if activity.last_seen is not None:
        gap = now - activity.last_seen
        if gap <= _MAX_ACTIVE_GAP_SECONDS:
            activity.active_seconds += gap

    activity.last_seen = now

    interval_seconds = settings.checkin_interval_minutes * 60
    if activity.active_seconds - activity.last_checkin_at_seconds >= interval_seconds:
        activity.checkin_due = True


def is_checkin_due(session_id: str) -> bool:
    activity = _sessions.get(session_id)
    return bool(activity and activity.checkin_due)


def reset_sessions_for_tests() -> None:
    _sessions.clear()


def submit_checkin(
    user_id: str,
    session_id: str,
    agent_id: str,
    completion_confirmation: bool,
    quality_rating: int,
    improvement_note: str,
    used_in_real_work: bool,
    willingness_to_pay: str,
    price_point_cents: Optional[int] = None,
) -> Dict[str, object]:
    """Validate and record a check-in, writing the verified outcome back
    onto this session's memory rows."""
    if not (1 <= quality_rating <= 5):
        raise CheckinValidationError("quality_rating must be between 1 and 5")
    if len(improvement_note.strip()) < 10:
        raise CheckinValidationError("improvement_note must be at least 10 characters")
    if willingness_to_pay not in ("yes", "no", "maybe"):
        raise CheckinValidationError("willingness_to_pay must be 'yes', 'no', or 'maybe'")

    row = {
        "user_id": user_id,
        "session_id": session_id,
        "agent_id": agent_id,
        "completed": completion_confirmation,
        "quality_rating": quality_rating,
        "improvement_note": improvement_note,
        "used_in_real_work": used_in_real_work,
        "willingness_to_pay": willingness_to_pay,
        "price_point_cents": price_point_cents,
    }

    memory_rows_updated = 0
    if is_configured():
        get_client().table("checkins").insert(row).execute()
        memory_rows_updated = mark_session_outcome(
            session_id, outcome_verified=completion_confirmation, quality_score=quality_rating
        )

    activity = _sessions.get(session_id)
    if activity:
        activity.checkin_due = False
        activity.last_checkin_at_seconds = activity.active_seconds

    return {"recorded": True, "memory_rows_updated": memory_rows_updated}
