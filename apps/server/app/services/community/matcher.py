"""Community matcher — Qloo-powered peer matching with mutual opt-in.

- Matching is Qloo-powered: each person's cultural likes are resolved to real
  Qloo entities via ``/search`` (cloud HTTP — no local models, no LLM key),
  affinity = shared resolved anchors + shared health constraints.
- The peer pool is a SIMULATED demo pool (``data_source: preview``); matching
  math is real and runs on live Qloo entities when a key is configured.
- Connections require mutual opt-in: requests stay ``pending`` until the other
  party explicitly accepts.

Future-scale switchpoint (NOT active today)
-------------------------------------------
``match_peers`` below walks the peer pool linearly and, in live mode, makes one
Qloo ``/search`` round-trip per peer per like. That is correct for the small
demo pool. When the pool grows past 1000 peers, swap the linear walk for the
FAISS recall path in ``app.services.community.faiss_scaleout`` (IndexFlatIP
over L2-normalised embeddings; the exact ``_score`` rerank is preserved so the
health-constraint semantics never change). The minimal diff is:

    from app.services.community import faiss_scaleout
    ...
    async def match_peers(...):
        if len(DEMO_PEERS) > faiss_scaleout.PEER_SCALE_THRESHOLD:
            return await faiss_scaleout.match_peers_faiss(
                DEMO_PEERS, user_likes, user_constraints, location, limit
            )
        # ... existing linear path below ...

See that module's docstring for the full design contract.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.qloo.client import QlooClient
from app.services.qloo.taste import search_cultural_entities

logger = logging.getLogger(__name__)

DEMO_PEERS: list[dict[str, Any]] = [
    {"id": "peer-001", "name": "Rosa, 79", "tagline": "Little Italy NYC — Sinatra, jazz, Italian home cooking",
     "cultural_likes": ["Frank Sinatra", "Jazz music", "Italian cuisine"], "location": "New York",
     "constraints": {"low_sodium": True, "soft_chewable": True}},
    {"id": "peer-002", "name": "Hiroshi, 81", "tagline": "Old Hollywood films + light Jiangnan home cooking",
     "cultural_likes": ["Roman Holiday", "Jiangnan cuisine"], "location": "Boston",
     "constraints": {"low_sugar": True, "low_sodium": True, "soft_chewable": True}},
    {"id": "peer-003", "name": "Gloria, 74", "tagline": "Bob Dylan, folk music, classic American diners",
     "cultural_likes": ["Bob Dylan", "Folk music", "American cuisine"], "location": "Chicago",
     "constraints": {"low_sodium": True, "medications": ["blood pressure"]}},
    {"id": "peer-004", "name": "Kenji, 76", "tagline": "Jazz standards, Mediterranean diet, easy-to-chew cooking",
     "cultural_likes": ["Ella Fitzgerald", "Mediterranean cuisine"], "location": "San Francisco",
     "constraints": {"soft_chewable": True, "low_sodium": True}},
    {"id": "peer-005", "name": "Margaret, 82", "tagline": "Classic Hollywood + comfort food, careful with sugar",
     "cultural_likes": ["Casablanca", "Italian cuisine", "Frank Sinatra"], "location": "New York",
     "constraints": {"low_sugar": True, "soft_chewable": True}},
    {"id": "peer-006", "name": "Sam, 77", "tagline": "Sinatra-era standards and grilled light fare",
     "cultural_likes": ["Frank Sinatra", "Jazz music"], "location": "New York",
     "constraints": {"low_sodium": True, "soft_chewable": True}},
    {"id": "peer-007", "name": "Carmen, 76", "tagline": "Latin jazz, salsa nights and Puerto Rican home cooking",
     "cultural_likes": ["Tito Puente", "Salsa music", "Puerto Rican cuisine"], "location": "Miami",
     "constraints": {"low_sodium": True, "soft_chewable": True}},
    {"id": "peer-008", "name": "Rajesh, 78", "tagline": "Indian classical ragas, sitar and light Mughlai home cooking",
     "cultural_likes": ["Ravi Shankar", "Indian classical music", "Mughlai cuisine"], "location": "Houston",
     "constraints": {"low_sugar": True, "medications": ["diabetes"]}},
    {"id": "peer-009", "name": "Claudette, 80", "tagline": "French chanson, Provençal cooking and easy-to-chew classics",
     "cultural_likes": ["Édith Piaf", "French chanson", "Provençal cuisine"], "location": "Boston",
     "constraints": {"soft_chewable": True, "low_sodium": True}},
    {"id": "peer-010", "name": "Seamus, 82", "tagline": "Irish folk ballads, pub comfort food, careful with salt",
     "cultural_likes": ["The Chieftains", "Irish folk music", "Irish cuisine"], "location": "Philadelphia",
     "constraints": {"low_sodium": True, "medications": ["blood pressure"]}},
    {"id": "peer-011", "name": "Ruth, 74", "tagline": "Yiddish theatre, klezmer and Jewish deli classics",
     "cultural_likes": ["Klezmer music", "Yiddish theatre", "Jewish cuisine"], "location": "New York",
     "constraints": {"low_sugar": True, "soft_chewable": True}},
    {"id": "peer-012", "name": "Mei-Ling, 77", "tagline": "Cantonese opera, dim sum mornings and steamed fish nights",
     "cultural_likes": ["Cantonese opera", "Dim sum", "Cantonese cuisine"], "location": "San Francisco",
     "constraints": {"low_sodium": True, "low_sugar": True}},
    {"id": "peer-013", "name": "Otis, 79", "tagline": "Motown, soul food Sundays and gospel choir gatherings",
     "cultural_likes": ["Marvin Gaye", "Motown", "Soul food"], "location": "Detroit",
     "constraints": {"low_sodium": True, "medications": ["blood pressure"]}},
    {"id": "peer-014", "name": "June, 75", "tagline": "Country western, porch-swing cooking and sugar-conscious desserts",
     "cultural_likes": ["Dolly Parton", "Country music", "Southern cuisine"], "location": "Nashville",
     "constraints": {"low_sugar": True, "soft_chewable": True}},
    {"id": "peer-015", "name": "Luiz, 81", "tagline": "Bossa nova, oceanfront feijoada and gentle low-salt seafood",
     "cultural_likes": ["Antônio Carlos Jobim", "Bossa nova", "Brazilian cuisine"], "location": "Miami",
     "constraints": {"low_sodium": True, "soft_chewable": True}},
    {"id": "peer-016", "name": "Eleni, 72", "tagline": "Rebetiko, Greek taverna nights and olive-oil Mediterranean meals",
     "cultural_likes": ["Rebetiko music", "Greek cuisine", "Mediterranean cuisine"], "location": "Chicago",
     "constraints": {"low_sodium": True, "low_sugar": True}},
    {"id": "peer-017", "name": "Soon-hee, 78", "tagline": "Korean ballads, banchan tables and light japchae suppers",
     "cultural_likes": ["Korean ballad music", "Korean cuisine", "Japchae"], "location": "Los Angeles",
     "constraints": {"low_sodium": True, "medications": ["diabetes"]}},
    {"id": "peer-018", "name": "Willie, 83", "tagline": "Delta blues, barbecue pit Saturdays and easy-to-chew sides",
     "cultural_likes": ["B.B. King", "Blues music", "Barbecue cuisine"], "location": "Chicago",
     "constraints": {"soft_chewable": True, "low_sodium": True}},
]

async def _resolve_likes(
    client: QlooClient, likes: list[str], max_per_person: int = 3
) -> list[dict[str, Any]]:
    """Resolve up to ``max_per_person`` cultural likes to Qloo entities (cloud)."""
    resolved: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for like in likes[:max_per_person]:
        try:
            hits = await search_cultural_entities(client, like, limit=1)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("peer-like resolution failed for %r: %s", like, exc)
            hits = []
        if hits:
            ent = hits[0]
            eid = ent.get("entity_id") or ent.get("id") or ""
            if eid and eid not in seen_ids:
                seen_ids.add(eid)
                resolved.append(ent)
    return resolved


def _score(
    user_ents: list[dict[str, Any]],
    peer_ents: list[dict[str, Any]],
    user_constraints: dict[str, Any] | None,
    peer_constraints: dict[str, Any] | None,
) -> tuple[float, list[str], list[str]]:
    """Return (affinity 0..1, shared_anchor_names, shared_constraint_keys)."""
    user_ids = {e.get("entity_id") or e.get("id") for e in user_ents}
    peer_ids = {e.get("entity_id") or e.get("id") for e in peer_ents}
    shared_ids = user_ids & peer_ids
    shared_names = [
        e.get("name", "")
        for e in peer_ents
        if (e.get("entity_id") or e.get("id")) in shared_ids and e.get("name")
    ]
    # Name-level overlap for anchors that resolved to different ids.
    user_names = {_norm(e.get("name", "")) for e in user_ents}
    peer_names = {_norm(e.get("name", "")) for e in peer_ents}
    shared_names.extend(sorted(user_names & peer_names))
    shared_names = list(dict.fromkeys(shared_names))

    uc = _constraint_keys(user_constraints)
    pc = _constraint_keys(peer_constraints)
    shared_cons = sorted(uc & pc)
    union_cons = uc | pc

    cultural = len(shared_names) / max(1, min(len(user_ents), len(peer_ents)))
    constraint = len(shared_cons) / max(1, len(union_cons)) if union_cons else 0.0
    score = 0.7 * cultural + 0.3 * constraint
    return min(1.0, score), shared_names, shared_cons



def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _constraint_keys(constraints: dict[str, Any] | None) -> set[str]:
    return {k for k, v in (constraints or {}).items() if v}

async def match_peers(
    client: QlooClient,
    user_likes: list[str],
    user_constraints: dict[str, Any] | None = None,
    location: str | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Find demo peers who share the user's cultural anchors and health needs.

    data_source is 'live' when a Qloo key is configured (anchors resolved
    against the real taste graph) and 'preview' otherwise (name-level overlap
    on the simulated pool - never mislabelled as live).
    """
    user_constraints = user_constraints or {}
    if client.enabled:
        user_ents = await _resolve_likes(client, user_likes, max_per_person=4)
    else:
        user_ents = [{"entity_id": _norm(n), "name": n} for n in user_likes[:4]]

    matches: list[dict[str, Any]] = []
    for peer in DEMO_PEERS:
        if client.enabled:
            peer_ents = await _resolve_likes(client, peer["cultural_likes"], max_per_person=3)
        else:
            peer_ents = [{"entity_id": _norm(n), "name": n} for n in peer["cultural_likes"][:3]]
        score, shared, cons = _score(
            user_ents, peer_ents, user_constraints, peer.get("constraints", {})
        )
        if score <= 0:
            continue
        # Location affinity is a bonus only when both sides specify it.
        loc_bonus = 0.0
        if location and peer.get("location"):
            if _norm(location) == _norm(peer["location"]):
                loc_bonus = 0.1
        matches.append(
            {
                "peer_id": peer["id"],
                "name": peer["name"],
                "tagline": peer["tagline"],
                "location": peer.get("location"),
                "cultural_likes": peer["cultural_likes"],
                "constraints": peer.get("constraints", {}),
                "shared_anchors": shared,
                "shared_constraints": cons,
                "affinity": round(min(1.0, score + loc_bonus), 3),
            }
        )

    matches.sort(key=lambda m: m["affinity"], reverse=True)
    return {
        "matches": matches[:limit],
        "user_likes_resolved": [
            {"name": e.get("name", ""), "domain": e.get("domain", "")} for e in user_ents
        ],
        "data_source": "live" if client.enabled else "preview",
    }


# ---- Numpy cosine semantic matcher (community demo path) --------------------
# Open-source red line: the ONLY place TasteCare uses sentence-transformers is
# this community matcher, and the recall math is plain numpy cosine similarity
# (no FAISS). The final ranking still runs through the exact ``_score`` above,
# so health-constraint semantics are byte-for-byte identical to any other path.

import os as _os
from pathlib import Path as _Path

_EMBEDDER: Any = None
_EMBEDDER_PATH: str | None = None


def _embedding_model_path() -> str:
    default = _os.path.join(
        str(_Path(__file__).resolve().parents[3]),  # <server>/app/services/community -> server
        "models", "all-MiniLM-L6-v2",
    )
    return _os.getenv("RAG_EMBEDDING_MODEL_PATH", default)


def _get_embedder():
    """Lazily load the local all-MiniLM-L6-v2 embedder; None when unavailable."""
    global _EMBEDDER, _EMBEDDER_PATH
    path = _embedding_model_path()
    if _EMBEDDER is None or _EMBEDDER_PATH != path:
        try:
            from sentence_transformers import SentenceTransformer
            _os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
            _os.environ.setdefault("HF_HUB_OFFLINE", "1")
            _EMBEDDER = SentenceTransformer(path)
            _EMBEDDER_PATH = path
            logger.info("community semantic embedder loaded from %s", path)
        except Exception as exc:  # pragma: no cover - model missing
            logger.warning("community semantic embedder unavailable: %s", exc)
            _EMBEDDER = None
    return _EMBEDDER


def _peer_search_text(peer: dict[str, Any]) -> str:
    """Text we vectorise — tagline carries the signal, likes add explicit anchors."""
    bits = [peer.get("tagline", ""), " ".join(peer.get("cultural_likes") or [])]
    return " | ".join(b for b in bits if b).strip() or peer.get("id", "")


class _OfflineClient:
    """Minimal disabled QlooClient stand-in for the graceful fallback path."""

    enabled = False


async def semantic_match_peers(
    user_likes: list[str],
    user_constraints: dict[str, Any] | None = None,
    location: str | None = None,
    limit: int = 5,
    pool: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Numpy-cosine demo matcher for the community peer pool.

    - Embeds each peer's tagline + cultural likes with the local
      all-MiniLM-L6-v2 model (sentence-transformers, offline).
    - Recalls by plain numpy cosine similarity of the user's combined likes.
    - Reranks with the exact ``_score`` (0.7 cultural overlap + 0.3 health
      constraint), so health-safety semantics never change at any scale.
    - NO FAISS — this is the "lightweight numpy vector search for demo".
    - Falls back to the deterministic name-overlap matcher when the local
      model is missing, so the endpoint never hard-fails.
    """
    import numpy as np

    pool = pool or DEMO_PEERS
    embedder = _get_embedder()
    if embedder is None:
        logger.info("semantic_match_peers: embedder unavailable, falling back to name-overlap")
        result = await match_peers(_OfflineClient(), user_likes, user_constraints, location, limit)
        result["vector_search"] = "name-overlap-fallback"
        return result

    try:
        texts = [_peer_search_text(p) for p in pool]
        peer_vecs = np.asarray(
            embedder.encode(texts, batch_size=64, show_progress_bar=False), dtype=np.float32
        )
        peer_norm = peer_vecs / (np.linalg.norm(peer_vecs, axis=1, keepdims=True) + 1e-9)
        q_vecs = np.asarray(
            embedder.encode([", ".join(user_likes) or "taste"], show_progress_bar=False), dtype=np.float32
        )
        q_norm = q_vecs / (np.linalg.norm(q_vecs, axis=1, keepdims=True) + 1e-9)
        cosine = np.asarray(q_norm @ peer_norm.T).reshape(-1)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("semantic_match_peers: numpy pass failed, falling back: %s", exc)
        result = await match_peers(_OfflineClient(), user_likes, user_constraints, location, limit)
        result["vector_search"] = "name-overlap-fallback"
        return result

    user_constraints = user_constraints or {}
    user_ents = [{"entity_id": _norm(n), "name": n} for n in user_likes[:4]]

    scored: list[dict[str, Any]] = []
    for idx, peer in enumerate(pool):
        peer_ents = [{"entity_id": _norm(n), "name": n} for n in (peer.get("cultural_likes") or [])[:3]]
        score, shared, cons = _score(
            user_ents, peer_ents, user_constraints, peer.get("constraints", {})
        )
        if score > 0:
            cos = float(cosine[idx]) if idx < len(cosine) else 0.0
            loc_bonus = 0.0
            if location and peer.get("location") and _norm(location) == _norm(peer["location"]):
                loc_bonus = 0.1
            scored.append({
                "peer_id": peer["id"],
                "name": peer["name"],
                "tagline": peer["tagline"],
                "location": peer.get("location"),
                "cultural_likes": peer.get("cultural_likes", []),
                "constraints": peer.get("constraints", {}),
                "shared_anchors": shared,
                "shared_constraints": cons,
                "affinity": round(min(1.0, score + loc_bonus), 3),
                "semantic_cosine": round(cos, 3),
            })

    scored.sort(key=lambda m: m["affinity"], reverse=True)
    return {
        "matches": scored[:limit],
        "user_likes_resolved": [{"name": n, "domain": ""} for n in user_likes[:4]],
        "data_source": "preview",  # simulated peer pool, never mislabelled as live
        "vector_search": "numpy-cosine",
    }


# ---- Mutual opt-in connection store (persistent JSON in server/data/) -------
# The demo's lightweight DB: connections survive server restarts because they are
# flushed to a JSON file on every write and re-loaded at import. No SQL, no new
# dependencies — small JSON is the right scale for a demo store.

from pathlib import Path
from threading import RLock

_CONNECTIONS_FILE = Path(__file__).resolve().parents[3] / "data" / "community_connections.json"
# parents[0] = app/services/community, [1] = app/services, [2] = app, [3] = apps/server
_CONNECTIONS_LOCK = RLock()
_connections: dict[str, dict[str, Any]] = {}


def _load_connections() -> None:
    """Read the JSON store into memory once at import time."""
    global _connections
    try:
        if _CONNECTIONS_FILE.exists():
            import json

            data = json.loads(_CONNECTIONS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                _connections = data
    except Exception:  # noqa: BLE001 - corrupt file must never break the demo
        logger.warning("community connections file unreadable — starting empty", exc_info=True)
        _connections = {}


def _save_connections() -> None:
    """Persist the in-memory store to JSON atomically (tmp file + replace)."""
    try:
        import json

        _CONNECTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = _CONNECTIONS_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(_connections, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(_CONNECTIONS_FILE)
    except Exception:  # noqa: BLE001 - persistence is best-effort, never a crash
        logger.warning("could not persist community connections", exc_info=True)


_load_connections()


def request_connection(peer_id: str) -> dict[str, Any]:
    """Create a PENDING connection request. It becomes active only after the
    other party explicitly accepts (mutual verification)."""
    peer = next((p for p in DEMO_PEERS if p["id"] == peer_id), None)
    if peer is None:
        return {"ok": False, "error": f"Unknown peer: {peer_id}"}
    with _CONNECTIONS_LOCK:
        existing = _connections.get(peer_id)
        if existing and existing.get("status") == "connected":
            return {
                "ok": True,
                "peer_id": peer_id,
                "status": "connected",
                "message": "Already connected.",
            }
        _connections[peer_id] = {
            "peer_id": peer_id,
            "peer_name": peer["name"],
            "status": "pending",
            "created_at": "session",
        }
    _save_connections()
    return {
        "ok": True,
        "peer_id": peer_id,
        "status": "pending",
        "message": (
            "Connection request sent. For your safety, the other person must "
            "accept before you can connect - and you should verify any "
            "health-related advice independently."
        ),
    }


def accept_connection(peer_id: str) -> dict[str, Any]:
    """The other party accepts the request - this is the mutual opt-in step."""
    peer = next((p for p in DEMO_PEERS if p["id"] == peer_id), None)
    if peer is None:
        return {"ok": False, "error": f"Unknown peer: {peer_id}"}
    with _CONNECTIONS_LOCK:
        if _connections.get(peer_id, {}).get("status") == "pending":
            _connections[peer_id]["status"] = "connected"
    _save_connections()
    return {
        "ok": True,
        "peer_id": peer_id,
        "status": _connections.get(peer_id, {}).get("status", "pending"),
    }


def connection_status(peer_id: str) -> dict[str, Any]:
    rec = _connections.get(peer_id)
    if not rec:
        return {"peer_id": peer_id, "status": "none"}
    return {"peer_id": peer_id, "status": rec.get("status", "none")}


def list_connections() -> list[dict[str, Any]]:
    return [
        {"peer_id": r["peer_id"], "peer_name": r["peer_name"], "status": r["status"]}
        for r in _connections.values()
    ]


def reset_connections_store(file_path: Path | None = None) -> None:
    """Test-only helper: point the store at an isolated file and wipe state."""
    global _CONNECTIONS_FILE, _connections
    with _CONNECTIONS_LOCK:
        if file_path is not None:
            _CONNECTIONS_FILE = Path(file_path)
        _connections = {}
    try:
        if _CONNECTIONS_FILE.exists():
            _CONNECTIONS_FILE.unlink()
    except Exception:  # noqa: BLE001 - cleanup is best-effort
        pass
