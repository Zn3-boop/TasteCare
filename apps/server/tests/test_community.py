"""Community matching + connection tests (offline — no Qloo key needed).

These verify the Qloo-powered matcher with a mocked client (name-level overlap
is the deterministic path) and the mutual opt-in connection flow.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock

SERVER_ROOT = Path(__file__).resolve().parent.parent
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from app.services.community.matcher import (
    accept_connection,
    match_peers,
    request_connection,
)


def _disabled_client():
    client = AsyncMock()
    client.enabled = False
    return client


async def test_match_peers_preview_overlap():
    """With no Qloo key (client disabled), matching runs on name overlap and is
    explicitly labelled preview — never mislabelled as live."""
    client = _disabled_client()
    result = await match_peers(
        client,
        ["Frank Sinatra", "Italian cuisine", "Jazz"],
        user_constraints={"low_sodium": True, "soft_chewable": True},
        location="New York",
    )
    assert result["data_source"] == "preview"
    assert result["matches"], "should find at least the Sinatra-overlapping peers"
    top = result["matches"][0]
    assert top["affinity"] > 0
    # Shared anchors must include the overlapping cultural name(s).
    assert any("Sinatra" in a for a in top["shared_anchors"])


async def test_match_peers_constraints_count_toward_score():
    """Peers sharing health constraints rank higher than those sharing only culture."""
    client = _disabled_client()
    r1 = await match_peers(
        client,
        ["Frank Sinatra"],
        user_constraints={"low_sodium": True, "soft_chewable": True},
        limit=10,
    )
    rosa = next((m for m in r1["matches"] if m["peer_id"] == "peer-001"), None)
    sam = next((m for m in r1["matches"] if m["peer_id"] == "peer-006"), None)
    assert rosa is not None and sam is not None
    # Rosa shares low_sodium + soft_chewable; Sam only low_sodium.
    assert rosa["affinity"] >= sam["affinity"]


async def test_connection_mutual_opt_in():
    """A request is PENDING until the other party explicitly accepts."""
    r = request_connection("peer-001")
    assert r["ok"] is True
    assert r["status"] == "pending"

    status_before_accept = None
    from app.services.community.matcher import connection_status
    status_before_accept = connection_status("peer-001")["status"]
    assert status_before_accept == "pending"

    acc = accept_connection("peer-001")
    assert acc["ok"] is True
    assert acc["status"] == "connected"
    assert connection_status("peer-001")["status"] == "connected"


async def test_unknown_peer_rejected():
    r = request_connection("peer-nope")
    assert r["ok"] is False
    assert "error" in r


async def test_demo_peer_pool_expanded():
    """P2: demo pool grew from 6 to 15-20 entries to feel more realistic."""
    from app.services.community.matcher import DEMO_PEERS
    assert len(DEMO_PEERS) >= 15
    ids = {p["id"] for p in DEMO_PEERS}
    assert len(ids) == len(DEMO_PEERS), "peer ids must be unique"
    # Legacy peers stay present (existing tests + connectors rely on them).
    assert "peer-001" in ids and "peer-006" in ids
    for p in DEMO_PEERS:
        assert p.get("tagline") and p.get("cultural_likes")


async def test_semantic_match_peers_numpy_cosine(monkeypatch):
    """with a fake embedder, the numpy-cosine path runs, ranks, and labels itself."""

    class _FakeEmbedder:
        def encode(self, texts, **kw):
            import numpy as np
            # deterministic pseudo-embeddings: each text's vector is one-hot-ish
            vecs = []
            for i, t in enumerate(texts):
                v = np.zeros(8, dtype=np.float32)
                v[i % 8] = 1.0
                v[0] += 0.1 * (i + 1)
                vecs.append(v)
            return np.asarray(vecs, dtype=np.float32)

    from app.services.community.matcher import semantic_match_peers
    monkeypatch.setattr("app.services.community.matcher._get_embedder", lambda: _FakeEmbedder())
    result = await semantic_match_peers(
        ["Frank Sinatra", "Jazz music"],
        user_constraints={"low_sodium": True, "soft_chewable": True},
        limit=5,
    )
    assert result["vector_search"] == "numpy-cosine"
    assert result["data_source"] == "preview"
    assert result["matches"], "numpy-cosine path should return matches"
    top = result["matches"][0]
    assert top["affinity"] > 0
    assert "semantic_cosine" in top


async def test_semantic_match_peers_falls_back_when_no_model(monkeypatch):
    """Missing local model -> deterministic name-overlap fallback, never a crash."""
    from app.services.community.matcher import semantic_match_peers
    monkeypatch.setattr("app.services.community.matcher._get_embedder", lambda: None)
    result = await semantic_match_peers(
        ["Frank Sinatra", "Italian cuisine"],
    )
    assert result["data_source"] == "preview"
    assert isinstance(result["matches"], list)
    assert "vector_search" in result  # fallback still returns the key for UI