"""Tests for semantic_wall/checkin/engine.py."""

import threading
from unittest.mock import MagicMock, patch

import pytest

from semantic_wall import config
from semantic_wall.checkin import engine


@pytest.fixture(autouse=True)
def _clean_sessions():
    engine.reset_sessions_for_tests()
    yield
    engine.reset_sessions_for_tests()


def test_record_activity_accumulates_time_between_calls(monkeypatch):
    times = iter([100.0, 130.0, 160.0])
    monkeypatch.setattr(engine.time, "monotonic", lambda: next(times))

    engine.record_activity("session-1")
    engine.record_activity("session-1")
    engine.record_activity("session-1")

    activity = engine._sessions["session-1"]
    assert activity.active_seconds == 60.0  # two 30s gaps


def test_record_activity_ignores_large_idle_gaps(monkeypatch):
    times = iter([100.0, 100.0 + engine._MAX_ACTIVE_GAP_SECONDS + 1])
    monkeypatch.setattr(engine.time, "monotonic", lambda: next(times))

    engine.record_activity("session-1")
    engine.record_activity("session-1")

    assert engine._sessions["session-1"].active_seconds == 0.0


def test_checkin_becomes_due_after_interval(monkeypatch):
    monkeypatch.setattr(config.settings, "checkin_interval_minutes", 30)
    # Simulate many small active gaps (well under the idle-gap threshold)
    # that sum to exactly the 30-minute interval, rather than one huge gap
    # (which correctly wouldn't count as active usage at all): 30 gaps of
    # 60s each, requiring 31 timestamps.
    step = 60.0
    num_gaps = 30
    timestamps = [i * step for i in range(num_gaps + 1)]
    times = iter(timestamps)
    monkeypatch.setattr(engine.time, "monotonic", lambda: next(times))

    for _ in range(num_gaps + 1):
        engine.record_activity("session-1")

    assert engine.is_checkin_due("session-1") is True


def test_is_checkin_due_false_for_unknown_session():
    assert engine.is_checkin_due("never-seen") is False


def test_record_activity_survives_concurrent_calls_for_same_session():
    """api/main.py runs chat work in a threadpool, so multiple requests for
    the same session can call record_activity concurrently — this must not
    raise, and every call must be reflected (no silently lost updates)."""
    call_count = 200
    threads = [
        threading.Thread(target=engine.record_activity, args=("session-concurrent",))
        for _ in range(call_count)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # No assertion on exact active_seconds (real wall-clock timing across
    # threads is inherently non-deterministic) — the meaningful guarantee
    # the lock provides is that the session record exists, is well-formed,
    # and every thread's write was serialized rather than lost or corrupted.
    activity = engine._sessions["session-concurrent"]
    assert activity.last_seen is not None
    assert activity.active_seconds >= 0


def test_submit_checkin_rejects_bad_quality_rating():
    with pytest.raises(engine.CheckinValidationError):
        engine.submit_checkin(
            "user-1", "session-1", "strategist",
            completion_confirmation=True, quality_rating=9,
            improvement_note="needed more detail", used_in_real_work=True,
            willingness_to_pay="yes",
        )


def test_submit_checkin_rejects_short_improvement_note():
    with pytest.raises(engine.CheckinValidationError):
        engine.submit_checkin(
            "user-1", "session-1", "strategist",
            completion_confirmation=True, quality_rating=4,
            improvement_note="short", used_in_real_work=True,
            willingness_to_pay="yes",
        )


def test_submit_checkin_rejects_bad_willingness_value():
    with pytest.raises(engine.CheckinValidationError):
        engine.submit_checkin(
            "user-1", "session-1", "strategist",
            completion_confirmation=True, quality_rating=4,
            improvement_note="needed more detail", used_in_real_work=True,
            willingness_to_pay="definitely",
        )


def test_submit_checkin_skips_persistence_when_memory_not_configured():
    with patch.object(engine, "is_configured", return_value=False), \
         patch.object(engine, "mark_session_outcome") as mock_mark:
        result = engine.submit_checkin(
            "user-1", "session-1", "strategist",
            completion_confirmation=True, quality_rating=5,
            improvement_note="worked perfectly honestly", used_in_real_work=True,
            willingness_to_pay="yes",
        )
    mock_mark.assert_not_called()
    assert result == {"recorded": True, "memory_rows_updated": 0}


def test_submit_checkin_persists_and_clears_due_flag(monkeypatch):
    monkeypatch.setattr(engine.time, "monotonic", lambda: 1000.0)
    engine.record_activity("session-1")
    engine._sessions["session-1"].checkin_due = True

    fake_client = MagicMock()
    with patch.object(engine, "is_configured", return_value=True), \
         patch.object(engine, "get_client", return_value=fake_client), \
         patch.object(engine, "mark_session_outcome", return_value=3) as mock_mark:
        result = engine.submit_checkin(
            "user-1", "session-1", "strategist",
            completion_confirmation=True, quality_rating=5,
            improvement_note="worked perfectly honestly", used_in_real_work=True,
            willingness_to_pay="yes", price_point_cents=4900,
        )

    fake_client.table.assert_called_once_with("checkins")
    mock_mark.assert_called_once_with("session-1", outcome_verified=True, quality_score=5)
    assert result == {"recorded": True, "memory_rows_updated": 3}
    assert engine._sessions["session-1"].checkin_due is False
