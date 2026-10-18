"""Future-scale FAISS path for peer matching — RECALL accelerator, NOT wired in.

Why this file exists
--------------------
`app.services.community.matcher.match_peers` walks the peer pool linearly and,
in live mode, makes one Qloo ``/search`` HTTP round-trip per peer per like. As
the pool grows, that is O(N) network calls plus O(N) Python score loops per
request. For the small demo pool that is exactly right — simple, auditable,
zero local models. This module is the *reviewed switchpoint* for a larger pool:
when ``len(peers) > PEER_SCALE_THRESHOLD``, recall moves to a FAISS
``IndexFlatIP`` over L2-normalised embeddings so per-request cost stays roughly
constant regardless of pool size.

``IndexFlatIP`` is itself brute-force (it scans every vector); FAISS's
amortised benefit only materialises above ~1k vectors where batched SIMD
inner products and the surrounding index bookkeeping outperform pure numpy.
Below the threshold the original numpy brute-force path has lower latency
because it avoids the one-time index construction overhead entirely.

Design contract (boundaries are deliberate)
-------------------------------------------
1. FAISS does RECALL only. The final ranking still runs through the existing
   ``_score`` (0.7 cultural + 0.3 health-constraint overlap), so TasteCare's
   health-safety semantics are byte-for-byte the same at any scale. We never
   let a raw vector score override constraint matching.
2. Texture ("soft chewable") and medication screening stay in their own
   modules; this path only accelerates candidate discovery.
3. Embedding uses the already-shipped local model
   (``RAG_EMBEDDING_MODEL_PATH``, default ``models/all-MiniLM-L6-v2``);
   ``faiss-cpu`` and ``sentence-transformers`` are already in
   ``requirements.txt`` — **no new dependency**.
4. Live mode: peer anchors must be pre-resolved ONCE at index-build time (the
   pool is re-embedded whenever it changes). Per-request live resolution of
   1000+ peers would recreate the exact O(N) network problem this file exists
   to solve, so the FAISS path documents preview / pre-resolved usage.

Switch condition (the comment at the top of ``match_peers`` in matcher.py)
--------------------------------------------------------------------------
    if len(peers) > faiss_scaleout.PEER_SCALE_THRESHOLD:
        return await faiss_scaleout.match_peers_faiss(
            peers, user_likes, user_constraints, location, limit
        )
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

#: When the peer pool grows past this many entries, switch the linear walk in
#: matcher.match_peers to this FAISS recall path.
#: 阈值仅作为工程切换参考，不是性能硬拐点，可根据压测微调。
PEER_SCALE_THRESHOLD: int = 1000

#: How many FAISS candidates to hand to the exact ``_score`` rerank. Recall is
#: cheap and parallel-friendly; the exact step is O(recall_factor * limit) max.
RECALL_FACTOR: int = 10


def _embedding_model_path() -> str:
    """Resolve the local embedding model like code_search / rag do."""
    default = os.path.join(
        str(Path(__file__).resolve().parents[3]),  # <server>/app/services/community → server
        "models", "all-MiniLM-L6-v2",
    )
    return os.getenv("RAG_EMBEDDING_MODEL_PATH", default)


#: Lazily loaded sentence-transformer (shared across requests; embedding is CPU
#: batched, which is plenty fast at the N>1000 cutoff for sub-second recall).
_EMBEDDER: Any = None
_EMBEDDER_PATH_SENTINEL: str | None = None


def _get_embedder():
    """Return the cached SentenceTransformer, loading it on first use."""
    global _EMBEDDER, _EMBEDDER_PATH_SENTINEL
    path = _embedding_model_path()
    if _EMBEDDER is None or _EMBEDDER_PATH_SENTINEL != path:
        from sentence_transformers import SentenceTransformer  # lazily; heavy import
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        _EMBEDDER = SentenceTransformer(path)
        _EMBEDDER_PATH_SENTINEL = path
        logger.info("faiss_scaleout: embedding model loaded from %s", path)
    return _EMBEDDER


def _peer_text(peer: dict[str, Any]) -> str:
    """Turn a peer record into the text we vectorise — tagline carries the
    signal, likes add explicit anchors, location is not taste so it stays out
    of the vector (it is already handled as a bonus in the exact rerank)."""
    bits = [peer.get("tagline", ""), " ".join(peer.get("cultural_likes") or [])]
    return " | ".join(b for b in bits if b).strip() or peer.get("id", "")


def build_peer_index(
    peers: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a FAISS IndexFlatIP over the peer pool.

    Returns {"index", "peers"} where ``index.ntotal == len(peers)``. The
    mapping is positional: ``index`` row ``i`` corresponds to ``peers[i]`` —
    rebuild (do not mutate) the pool when peers change.
    """
    import faiss
    import numpy as np

    texts = [_peer_text(p) for p in peers]
    vecs = _get_embedder().encode(texts, batch_size=64, show_progress_bar=False)
    vecs = np.asarray(vecs, dtype=np.float32)
    faiss.normalize_L2(vecs)  # L2 -> IndexFlatIP inner product == cosine sim.
    dim = vecs.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(vecs)
    logger.info("faiss_scaleout: built index of %d peers, dim=%d", index.ntotal, dim)
    return {"index": index, "peers": peers}


def _recall(
    built: dict[str, Any],
    query_text: str,
    top_k: int,
) -> list[tuple[float, dict[str, Any]]]:
    """Return [(cosine, peer)] for the top_k nearest peers."""
    import faiss
    import numpy as np

    q = np.asarray(_get_embedder().encode([query_text]), dtype=np.float32)
    faiss.normalize_L2(q)
    index: Any = built["index"]
    scores, idxs = index.search(q, min(top_k, index.ntotal))
    return [
        (float(s), built["peers"][i])
        for s, i in zip(scores[0], idxs[0])
        if i >= 0
    ]


async def match_peers_faiss(
    peers: list[dict[str, Any]],
    user_likes: list[str],
    user_constraints: dict[str, Any] | None = None,
    location: str | None = None,
    limit: int = 5,
    built: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Callers keep the same response shape as ``matcher.match_peers`` so the
    API layer never knows which path ran. Preview-mode anchor representation
    matches matcher._resolve_likes' offline branch exactly.

    ``built`` lets a hot caller reuse a prebuilt index (rebuild only when the
    pool changes); when omitted we build here for self-contained use.
    """
    from app.services.community.matcher import _norm, _score

    built = built or build_peer_index(peers)
    query_text = " | ".join(b for b in [", ".join(user_likes)] if b).strip() or "(me)"
    recall_k = max(limit * RECALL_FACTOR, limit)
    user_ents = [
        {"entity_id": _norm(n), "name": n}
        for n in (user_likes or [])[:4]
    ]

    matches: list[dict[str, Any]] = []
    for _cosine, peer in _recall(built, query_text, top_k=recall_k):
        peer_ents = [
            {"entity_id": _norm(n), "name": n}
            for n in (peer.get("cultural_likes") or [])[:3]
        ]
        score, shared, cons = _score(
            user_ents, peer_ents, user_constraints or {}, peer.get("constraints", {})
        )
        if score <= 0:
            continue
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
                # recall vector score exposed for observability only — the
                # affinity above is always the _score contract.
                "vector_score": round(float(_cosine), 4),
            }
        )

    matches.sort(key=lambda m: m["affinity"], reverse=True)
    return {
        "matches": matches[:limit],
        "user_likes_resolved": [
            {"name": e.get("name", ""), "domain": e.get("domain", "")} for e in user_ents
        ],
        "data_source": "preview",  # FAISS path = pre-resolved anchors; see docstring.
        "scaled": True,
    }