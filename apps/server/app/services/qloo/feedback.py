"""In-memory Qloo taste feedback store (preview / live dual-mode).

Constraints honored:
- Session-lifetime, in-process only. NEVER persisted to disk and NEVER holds real
  personal data (consistent with the "no real user data" hackathon rule).
- Preview mode (no QLOO_API_KEY): feedback only adjusts an in-memory Maria demo
  taste pool so the whole agent loop can be exercised offline.
- Live mode: the same feedback would be forwarded to Qloo's taste-profile update
  endpoint (wiring documented in executor._exec_qloo_update_taste).

DI structure (P3 feedback-store refactor):
- `FeedbackStore` is the thread-safe, per-session store class (RLock-guarded).
- `FeedbackStoreRegistry` + `get_feedback_store()` form the session-keyed,
  cross-request dependency registry: endpoints / graph nodes obtain their
  session's store here and thread it explicitly through apply_taste_preferences
  / qloo_cultural_recommend_node. `reset_feedback_stores()` drops stores
  (tests / logout). No module-level pools or shim functions remain.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class FeedbackStore:
    """Per-session in-memory store of the user's 👍/👎 taste feedback.

    Thread-safety: every public read/write is guarded by an RLock — FastAPI runs
    sync handlers on a thread pool, so instance state must be safe under
    concurrent access. RLock (not Lock) is a deliberate defensive choice: it
    stays correct even if methods are composed later (e.g. a public method
    calling another public method of the same store).
    """

    def __init__(self, session_id: str = "default", ttl_seconds: int | None = None) -> None:
        self.session_id = session_id
        self._ttl_seconds = ttl_seconds
        self._created_at = datetime.now(timezone.utc)
        self._lock = threading.RLock()

        # key: message_id (client-generated, opaque) -> feedback record
        self._feedback_records: dict[str, dict[str, Any]] = {}

        # entity name -> cumulative weight delta applied to the preview taste pool
        self._preview_pool_deltas: dict[str, float] = {}

        # ===== Live taste-preference layer =====
        # Qloo's hackathon API has NO remote "write taste profile" endpoint (the
        # /recs and /recommendations write paths are legacy and unsupported). The
        # honest live-mode implementation is therefore a LOCAL preference overlay
        # that is applied to every subsequent /v2/insights call:
        #   - liked   entity names -> resolved to Qloo entity UUIDs and prepended
        #     to `signal.interests.entities` (highest-weight signals).
        #   - disliked entity names -> resolved to UUIDs and hard-filtered OUT of
        #     every subsequent recommendation result (client-side exclusion).
        # Both pools are keyed by the entity NAME the user saw (stable for the
        # UI), not by message_id, so repeated 👍/👎 on the same entity accumulate.
        # Session-lifetime only, never persisted.
        self._liked_taste_names: dict[str, float] = {}   # name -> weight (default 1.0)
        self._disliked_taste_names: dict[str, float] = {}  # name -> weight (default 1.0)

    # -- lifecycle ---------------------------------------------------------

    def is_expired(self) -> bool:
        """TTL guard for session-scoped instances (a background reaper may call this)."""
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
        """Record one like/dislike for a recommendation. Returns the stored record.

        Records are keyed by the (opaque, client-generated) message_id. As a
        defensive guard, a blank message_id still records but under a generated
        key. Also feeds the live preference overlay (liked/disliked pools) so
        subsequent /v2/insights calls are re-weighted.
        """
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

            # Update the in-memory preview taste pool (session-lifetime only).
            delta = 1.0 if thumb == "up" else -0.5
            for e in entities:
                self._preview_pool_deltas[e] = self._preview_pool_deltas.get(e, 0.0) + delta
                # Also maintain the live preference overlay.
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
# -- read paths ---------------------------------------------------------

    def get_liked_taste_names(self) -> dict[str, float]:
        """Entity names the user 👍'd, with accumulated weight."""
        with self._lock:
            return dict(self._liked_taste_names)

    def get_disliked_taste_names(self) -> dict[str, float]:
        """Entity names the user 👎'd, with accumulated weight."""
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
# Session-keyed dependency registry (P3 DI refactor).
#
# The registry is the ONLY module-level mutable object left: it maps a
# session_id to a long-lived FeedbackStore instance so the same session's
# feedback survives across requests inside one process (cross-request
# persistence). Endpoints / graph nodes obtain their store via
# get_feedback_store() and thread it explicitly through apply_taste_preferences
# / qloo_cultural_recommend_node — no other module reads or writes feedback
# state directly.
# ---------------------------------------------------------------------------


class FeedbackStoreRegistry:
    """Thread-safe registry of session-scoped FeedbackStore instances.

    Cross-request persistence: a store lives until its TTL elapses or
    reset_feedback_stores() drops it (tests / logout). Two different
    session_ids never share pools.
    """

    def __init__(self, ttl_seconds: int | None = 3600) -> None:
        self._lock = threading.RLock()
        self._ttl_seconds = ttl_seconds
        self._stores: dict[str, FeedbackStore] = {}

    def get(self, session_id: str | None = None) -> FeedbackStore:
        key = (session_id or "default").strip() or "default"
        with self._lock:
            store = self._stores.get(key)
            if store is None or store.is_expired():
                store = FeedbackStore(session_id=key, ttl_seconds=self._ttl_seconds)
                self._stores[key] = store
            return store

    def reset(self, session_id: str | None = None) -> None:
        """Drop one session's store, or the whole registry when session_id is None."""
        with self._lock:
            if session_id is None:
                self._stores.clear()
            else:
                key = (session_id or "default").strip() or "default"
                self._stores.pop(key, None)


_REGISTRY = FeedbackStoreRegistry()


def get_feedback_store(session_id: str | None = None) -> FeedbackStore:
    """Return the persistent FeedbackStore for a session (default: 'default')."""
    return _REGISTRY.get(session_id)


def reset_feedback_stores(session_id: str | None = None) -> None:
    """Drop one session's store or the whole registry (tests / session logout)."""
    _REGISTRY.reset(session_id)