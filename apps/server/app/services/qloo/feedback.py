"""In-memory Qloo taste feedback store (preview / live dual-mode).

Constraints honored:
- Session-lifetime, in-process only. NEVER persisted to disk and NEVER holds real
  personal data (consistent with the "no real user data" hackathon rule).
- Preview mode (no QLOO_API_KEY): feedback only adjusts an in-memory Maria demo
  taste pool so the whole agent loop can be exercised offline.
- Live mode: the same feedback would be forwarded to Qloo's taste-profile update
  endpoint (wiring documented in executor._exec_qloo_update_taste).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# key: message_id (client-generated, opaque) -> feedback record
_feedback_records: dict[str, dict[str, Any]] = {}

# entity name -> cumulative weight delta applied to the preview taste pool
_preview_pool_deltas: dict[str, float] = {}

# ===== Live taste-preference layer =====
# Qloo's hackathon API has NO remote "write taste profile" endpoint (the /recs and
# /recommendations write paths are legacy and unsupported). The honest live-mode
# implementation is therefore a LOCAL preference overlay that is applied to every
# subsequent /v2/insights call:
#   - liked   entity names -> resolved to Qloo entity UUIDs and prepended to
#     `signal.interests.entities` (highest-weight signals) on the next insights call.
#   - disliked entity names -> resolved to UUIDs and hard-filtered OUT of every
#     subsequent recommendation result (client-side exclusion).
# Both pools are keyed by the entity NAME the user saw (stable for the UI), not by
# message_id, so repeated 👍/👎 on the same entity accumulate. Session-lifetime only,
# never persisted — consistent with the "no real user data" hackathon rule.
_liked_taste_names: dict[str, float] = {}   # entity name -> weight (default 1.0)
_disliked_taste_names: dict[str, float] = {}  # entity name -> weight (default 1.0)


def record_feedback(
    message_id: str,
    thumb: str,
    taste_entities: list[str] | None = None,
) -> dict[str, Any]:
    """Record one like/dislike for a recommendation. Returns the stored record.

    Records are keyed by the (opaque, client-generated) message_id. As a
    defensive guard, a blank message_id still records but under a generated key.
    Also feeds the live preference overlay (liked/disliked pools) so subsequent
    /v2/insights calls are re-weighted.
    """
    key = (message_id or "").strip() or f"anon-{datetime.now(timezone.utc).timestamp()}"
    thumb = "up" if thumb == "up" else "down"
    entities = [str(e).strip() for e in (taste_entities or []) if str(e).strip()]

    record: dict[str, Any] = {
        "message_id": key,
        "thumb": thumb,
        "taste_entities": entities,
        "at": datetime.now(timezone.utc).isoformat(),
    }
    _feedback_records[key] = record

    # Update the in-memory preview taste pool (session-lifetime only).
    delta = 1.0 if thumb == "up" else -0.5
    for e in entities:
        _preview_pool_deltas[e] = _preview_pool_deltas.get(e, 0.0) + delta
        # Also maintain the live preference overlay (used when Qloo is enabled).
        if thumb == "up":
            _liked_taste_names[e] = _liked_taste_names.get(e, 0.0) + 1.0
            _disliked_taste_names.pop(e, None)
        else:
            _disliked_taste_names[e] = _disliked_taste_names.get(e, 0.0) + 1.0
            _liked_taste_names.pop(e, None)

    logger.info(
        "[QlooFeedback] recorded thumb=%s message_id=%s entities=%d data_source=%s",
        thumb,
        key,
        len(entities),
        "preview",
    )
    return record


def get_liked_taste_names() -> dict[str, float]:
    """Entity names the user 👍'd, with accumulated weight."""
    return dict(_liked_taste_names)


def get_disliked_taste_names() -> dict[str, float]:
    """Entity names the user 👎'd, with accumulated weight."""
    return dict(_disliked_taste_names)


def get_feedback_records() -> dict[str, dict[str, Any]]:
    return dict(_feedback_records)


def get_preview_pool_deltas() -> dict[str, float]:
    return dict(_preview_pool_deltas)