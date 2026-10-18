"""FeedbackStore (P3 Phase 1) — isolation, concurrency, and semantics tests.

Covers the class introduced by the DI refactor plus the session-keyed registry
(get_feedback_store / reset_feedback_stores). The conftest autouse fixture
resets the registry before every test; these tests deliberately use *fresh*
FeedbackStore instances (per-session isolation) and touch the registry only
where the dependency-injection layer itself is the subject under test.
"""
from __future__ import annotations

import threading

from app.services.qloo.feedback import (
    FeedbackStore,
    get_feedback_store,
    reset_feedback_stores,
)


# ═══════════════════════════════════════════════════════════════════════════
# 1. Session isolation — two instances never share state
# ═══════════════════════════════════════════════════════════════════════════


def test_sessions_are_isolated() -> None:
    a = FeedbackStore(session_id="session-a")
    b = FeedbackStore(session_id="session-b")

    a.record_feedback("m1", "up", ["Radiohead"])
    b.record_feedback("m2", "down", ["Muse"])

    assert a.get_liked_taste_names() == {"Radiohead": 1.0}
    assert a.get_disliked_taste_names() == {}
    assert b.get_liked_taste_names() == {}
    assert b.get_disliked_taste_names() == {"Muse": 1.0}


def test_session_id_is_echoed_in_repr() -> None:
    s = FeedbackStore(session_id="sess-42")
    assert "sess-42" in repr(s)


# ═══════════════════════════════════════════════════════════════════════════
# 2. Data-model red lines — dict[str, float] pools / dict[str, dict] records
# ═══════════════════════════════════════════════════════════════════════════


def test_multiple_likes_accumulate_weight() -> None:
    s = FeedbackStore(session_id="accum")
    s.record_feedback("m1", "up", ["Classical"])
    s.record_feedback("m2", "up", ["Classical"])

    liked = s.get_liked_taste_names()
    assert liked == {"Classical": 2.0}


def test_like_dislike_moves_between_pools() -> None:
    s = FeedbackStore(session_id="move")
    s.record_feedback("m1", "down", ["Muse"])
    s.record_feedback("m2", "up", ["Muse"])

    assert "Muse" not in s.get_disliked_taste_names()
    assert s.get_liked_taste_names() == {"Muse": 1.0}


def test_dislike_applies_negative_delta_to_preview_pool() -> None:
    s = FeedbackStore(session_id="delta")
    s.record_feedback("m1", "up", ["Jiangnan light braised cuisine"])
    s.record_feedback("m2", "down", ["Jiangnan light braised cuisine"])

    assert s.get_preview_pool_deltas()["Jiangnan light braised cuisine"] == 0.5


def test_blank_message_id_gets_generated_key() -> None:
    s = FeedbackStore(session_id="anon")
    rec = s.record_feedback("", "up", ["Totoro"])
    assert rec["message_id"].startswith("anon-")
    assert rec["message_id"] in s.get_feedback_records()


def test_returns_a_copy_not_the_internal_dict() -> None:
    s = FeedbackStore(session_id="copy")
    s.record_feedback("m1", "up", ["Radiohead"])
    liked = s.get_liked_taste_names()
    liked["Hacked"] = 99.0
    assert "Hacked" not in s.get_liked_taste_names()


# ═══════════════════════════════════════════════════════════════════════════
# 4. Concurrency — many threads hammering record/read stay consistent
# ═══════════════════════════════════════════════════════════════════════════


def test_concurrent_record_and_read_are_consistent() -> None:
    s = FeedbackStore(session_id="concurrent")
    n_threads = 8
    per_thread = 25
    barrier = threading.Barrier(n_threads)

    def worker(idx: int) -> None:
        barrier.wait()
        for i in range(per_thread):
            s.record_feedback(f"t{idx}-{i}", "up", ["Radiohead", "Classical"])

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    expected = n_threads * per_thread
    liked = s.get_liked_taste_names()
    assert liked["Radiohead"] == expected
    assert liked["Classical"] == expected
    assert len(s.get_feedback_records()) == expected


def test_concurrent_writes_and_reads_do_not_raise() -> None:
    import time

    s = FeedbackStore(session_id="rw")
    stop = threading.Event()
    errors: list[Exception] = []

    def writer() -> None:
        i = 0
        while not stop.is_set():
            s.record_feedback(f"w-{i}", "up" if i % 2 == 0 else "down", ["Muse"])
            i += 1

    def reader() -> None:
        while not stop.is_set():
            try:
                s.get_liked_taste_names()
                s.get_disliked_taste_names()
                s.get_feedback_records()
                s.get_preview_pool_deltas()
            except Exception as e:  # pragma: no cover - assertion below
                errors.append(e)

    threads = [
        threading.Thread(target=writer),
        threading.Thread(target=reader),
        threading.Thread(target=reader),
    ]
    for t in threads:
        t.start()
    time.sleep(0.05)
    stop.set()
    for t in threads:
        t.join()

    assert errors == []
    assert s.get_feedback_records() != {}


# ═══════════════════════════════════════════════════════════════════════════
# 5. Session-keyed DI registry — cross-request persistence + isolation
# ═══════════════════════════════════════════════════════════════════════════


def test_get_feedback_store_persists_across_calls() -> None:
    """The DI registry returns the SAME default-session store across calls."""
    reset_feedback_stores()
    store = get_feedback_store()
    store.record_feedback("shim-1", "up", ["Ella Fitzgerald"])
    again = get_feedback_store()
    assert again is store
    assert again.get_liked_taste_names().get("Ella Fitzgerald") == 1.0
    assert "Ella Fitzgerald" in again.get_feedback_records()["shim-1"]["taste_entities"]
    assert again.get_preview_pool_deltas().get("Ella Fitzgerald") == 1.0


def test_registry_keyed_by_session_id() -> None:
    """Two different session_ids get distinct persistent stores; the same id reuses one."""
    reset_feedback_stores()
    a1 = get_feedback_store("session-a")
    a2 = get_feedback_store("session-a")
    b = get_feedback_store("session-b")
    assert a1 is a2
    assert a1 is not b
    a1.record_feedback("m1", "up", ["Radiohead"])
    b.record_feedback("m2", "down", ["Muse"])
    assert b.get_liked_taste_names() == {}
    assert b.get_disliked_taste_names() == {"Muse": 1.0}
    assert a1.get_liked_taste_names() == {"Radiohead": 1.0}


def test_registry_blank_thumb_means_dislike() -> None:
    reset_feedback_stores()
    get_feedback_store().record_feedback("shim-down", "anything-else", ["Muse"])
    assert get_feedback_store().get_disliked_taste_names().get("Muse") == 1.0
# ═══════════════════════════════════════════════════════════════════════════
# 3. Lifecycle — clear_all and TTL
# ═══════════════════════════════════════════════════════════════════════════


def test_clear_all_resets_every_pool() -> None:
    s = FeedbackStore(session_id="reset")
    s.record_feedback("m1", "up", ["Radiohead"])
    s.clear_all()
    assert s.get_feedback_records() == {}
    assert s.get_liked_taste_names() == {}
    assert s.get_disliked_taste_names() == {}
    assert s.get_preview_pool_deltas() == {}


def test_ttl_guard_no_ttl_never_expires() -> None:
    s = FeedbackStore(session_id="no-ttl")
    assert s.is_expired() is False


def test_ttl_guard_with_ttl_expires() -> None:
    s = FeedbackStore(session_id="ttl", ttl_seconds=-1)
    assert s.is_expired() is True


def test_ttl_guard_tracks_creation_time() -> None:
    # is_expired uses _created_at; a fresh store with a huge TTL is not expired.
    s = FeedbackStore(session_id="ttl-fresh", ttl_seconds=3600)
    assert s.is_expired() is False
