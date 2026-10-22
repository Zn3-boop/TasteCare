"""DRAFT — NOT wired into the app. FeedbackStore class-based refactor (Phase 1).

Design artifact for docs/backlog/p3-feedback-store-di-refactor.md. It is
intentionally NOT imported by application code: the module-level shim below
reproduces feedback.py's current public API so existing callers (chat.py,
tastecare.py, taste.py, tests) keep working during migration.

Facts this draft aligns with (verified against app/services/qloo/feedback.py):
- The mutable pools are module-level dicts today; there is NO FeedbackStore
  class yet — this file introduces it.
- Method semantics mirror the current module functions EXACTLY so behavior is
  byte-for-byte compatible.
- A lock guards every method: FastAPI runs sync handlers in a thread pool, so
  instance state must be safe from concurrent access too.
- Data model red lines (do NOT "simplify"):
    liked/disliked  -> dict[str, float] weight pools (test asserts 2.0 after
                       two likes of the same name; a set would break it)
    feedback records-> dict[str, dict] keyed by message_id (blank ids get
                       an auto "anon-*" key; a list would break it)
- Compat-layer red line: production exports are the MODULE-LEVEL FUNCTIONS
  (record_feedback / get_liked_taste_names / get_disliked_taste_names /
  get_feedback_records / get_preview_pool_deltas). There is NO "feedback_store"
  global name in production — it only exists as a test alias
  ("import feedback as feedback_store"). Keep the functions, not just a name.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class FeedbackStore:
    """Per-session in-memory store of the user's 👍/👎 taste feedback.

    One instance per session/request (via DI in Phase 2); the class is
    self-contained and thread-safe by construction.
    """

    def __init__(self, session_id: str = "default", ttl_seconds: int | None = None) -> None:
        self.session_id = session_id
        self._ttl_seconds = ttl_seconds
        self._created_at = datetime.now(timezone.utc)
        self._lock = threading.RLock()
        self._feedback_records: dict[str, dict[str, Any]] = {}
        self._preview_pool_deltas: dict[str, float] = {}
        self._liked_taste_names: dict[str, float] = {}
        self._disliked_taste_names: dict[str, float] = {}

    # -- lifecycle ---------------------------------------------------------

    def is_expired(self) -> bool:
        """TTL guard for session-scoped instances (background reaper may call this)."""
        if self._ttl_seconds is None:
            return False
        age = (datetime.now(timezone.utc) - self._created_at).total_seconds()
        return age > self._ttl_seconds

    def clear_all(self) -> None:
        """Full reset — used by tests; also safe for a session "logout" wipe."""
        with self._lock:
            self._feedback_records.clear()
            self._preview_pool_deltas.clear()
            self._liked_taste_names.clear()
            self._disliked_taste_names.clear()

    # -- core write path ---------------------------------------------------

    def record_feedback(
        self,
        message_id: str,
        thumb: str,
        taste_entities: list[str] | None = None,
    ) -> dict[str, Any]:
        """Record one like/dislike. Same semantics as feedback.record_feedback today."""
        with self._lock:
            key = (message_id or "").strip() or f"anon-{datetime.now(timezone.utc).timestamp()}"
            thumb = "up" if thumb == "up" else "down"
            entities = [str(e).strip() for e in (taste_entities or []) if str(e).strip()]

            record: dict[str, Any] = {
                "message_id": key,
                "thumb": thumb,
                "taste_entities": entities,
                "at": datetime.now(timezone.utc).isoformat(),
            }
            self._feedback_records[key] = record

            delta = 1.0 if thumb == "up" else -0.5
            for e in entities:
                self._preview_pool_deltas[e] = self._preview_pool_deltas.get(e, 0.0) + delta
                if thumb == "up":
                    self._liked_taste_names[e] = self._liked_taste_names.get(e, 0.0) + 1.0
                    self._disliked_taste_names.pop(e, None)
                else:
                    self._disliked_taste_names[e] = self._disliked_taste_names.get(e, 0.0) + 1.0
                    self._liked_taste_names.pop(e, None)

            logger.info(
                "[QlooFeedback] recorded thumb=%s message_id=%s entities=%d data_source=%s",
                thumb,
                key,
                len(entities),
                "preview",
            )
            return dict(record)

    # -- read paths ----------------------------------------------------------

    def get_liked_taste_names(self) -> dict[str, float]:
        with self._lock:
            return dict(self._liked_taste_names)

    def get_disliked_taste_names(self) -> dict[str, float]:
        with self._lock:
            return dict(self._disliked_taste_names)

    def get_feedback_records(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return dict(self._feedback_records)

    def get_preview_pool_deltas(self) -> dict[str, float]:
        with self._lock:
            return dict(self._preview_pool_deltas)

    def __repr__(self) -> str:
        return (
            f"<FeedbackStore session={self.session_id!r} "
            f"liked={len(self._liked_taste_names)} disliked={len(self._disliked_taste_names)}>"
        )


# ---------------------------------------------------------------------------
# Phase-1 backward-compatible module-level shim (delegates to a default store).
# Phase 3 removes this whole section once every caller uses injected instances.
# ---------------------------------------------------------------------------
_DEFAULT_STORE = FeedbackStore(session_id="default")


def record_feedback(
    message_id: str,
    thumb: str,
    taste_entities: list[str] | None = None,
) -> dict[str, Any]:
    """Deprecated compat shim — delegates to the module default store."""
    import warnings

    warnings.warn(
        "record_feedback is deprecated; inject a FeedbackStore instance instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return _DEFAULT_STORE.record_feedback(message_id, thumb, taste_entities)


def get_liked_taste_names() -> dict[str, float]:
    return _DEFAULT_STORE.get_liked_taste_names()


def get_disliked_taste_names() -> dict[str, float]:
    return _DEFAULT_STORE.get_disliked_taste_names()


def get_feedback_records() -> dict[str, dict[str, Any]]:
    return _DEFAULT_STORE.get_feedback_records()


def get_preview_pool_deltas() -> dict[str, float]:
    return _DEFAULT_STORE.get_preview_pool_deltas()


# ---------------------------------------------------------------------------
# Phase-2 DI wiring sketch (FastAPI) — NOT enabled yet.
#
#   async def get_feedback_store(request: Request) -> FeedbackStore:
#       """Per-session instance, cached for the request lifetime."""
#       session_id = getattr(request.state, "session_id", "default")
#       store = getattr(request.state, "_feedback_store", None)
#       if store is None:
#           store = FeedbackStore(session_id=session_id, ttl_seconds=3600)
#           request.state._feedback_store = store
#       return store
#
# Endpoints then declare `store: FeedbackStore = Depends(get_feedback_store)`.
# For LangGraph, inject the instance explicitly into AgentState at build time
# (nodes have no FastAPI Depends):
#
#   node_state = {
#       "raw_query": payload.message,
#       "entities": {"cultural_likes": likes, "target_domain": ...},
#       "feedback_store": store,   # <-- qloo_cultural_recommend_node reads this
#   }
#
# Phase-3 persistence swap: implement the same public method set against Redis/DB
# behind a Repository protocol; FeedbackStore signatures stay stable so callers
# are unaffected.
# ---------------------------------------------------------------------------
