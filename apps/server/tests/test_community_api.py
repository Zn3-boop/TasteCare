"""Community API integration tests (offline — mocked Qloo client)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

SERVER_ROOT = Path(__file__).resolve().parent.parent
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from app.main import app  # noqa: E402
from app.services.community.matcher import _connections  # noqa: E402

client = TestClient(app)


def _enabled_client():
    mock = AsyncMock()
    mock.enabled = True

    async def fake_search(client_, query, limit=1):
        name = query.strip()
        return [{
            "entity_id": f"urn:{name.lower().replace(' ', '-')}",
            "name": name,
            "type": "urn:entity:artist",
            "domain": "music",
        }]

    async def fake_recs(client_, seed_ids, target_domain=None, limit=10):
        return {"recommendations": [{"name": "Carmine's", "popularity": 0.9}]}

    mock.search_cultural_entities = AsyncMock(side_effect=fake_search)
    return mock


def _disabled_client():
    mock = AsyncMock()
    mock.enabled = False
    return mock


def test_community_match_preview_without_qloo():
    """No Qloo key -> preview data_source is returned (honest label), never live."""
    with patch("app.api.community.get_qloo_client", return_value=_disabled_client()):
        resp = client.post(
            "/api/v1/community/match",
            json={
                "cultural_likes": ["Frank Sinatra", "Italian cuisine"],
                "location": "New York",
                "constraints": {"low_sodium": True, "soft_chewable": True},
            },
        )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["data_source"] == "preview"
    assert isinstance(payload["matches"], list) and payload["matches"]


def test_community_match_live_with_qloo():
    """With Qloo enabled the endpoint labels result live and resolves user likes."""

    async def fake_search(client_, query, limit=1):
        name = query.strip()
        return [{
            "entity_id": f"urn:{name.lower().replace(' ', '-')}",
            "name": name,
            "type": "urn:entity:artist",
            "domain": "music",
        }]

    mock = _enabled_client()
    with patch("app.api.community.get_qloo_client", return_value=mock), \
         patch("app.services.community.matcher.search_cultural_entities", side_effect=fake_search):
        resp = client.post(
            "/api/v1/community/match",
            json={
                "cultural_likes": ["Frank Sinatra", "Jazz"],
                "location": "New York",
                "constraints": {"low_sodium": True},
            },
        )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["data_source"] == "live"
    assert payload["matches"], payload
    assert payload["user_likes_resolved"]


def test_community_connect_requires_accept():
    """Connect request stays pending until /accept (mutual opt-in)."""
    _connections.clear()
    with patch("app.api.community.get_qloo_client", return_value=_disabled_client()):
        r1 = client.post("/api/v1/community/connect", json={"peer_id": "peer-001"})
        assert r1.status_code == 200, r1.text
        assert r1.json()["status"] == "pending"

        a = client.post("/api/v1/community/accept", json={"peer_id": "peer-001"})
        assert a.status_code == 200, a.text
        assert a.json()["status"] == "connected"

        conns = client.get("/api/v1/community/connections").json()
        assert any(c["peer_id"] == "peer-001" and c["status"] == "connected" for c in conns["connections"])


def test_community_connect_unknown_peer():
    _connections.clear()
    with patch("app.api.community.get_qloo_client", return_value=_disabled_client()):
        r = client.post("/api/v1/community/connect", json={"peer_id": "peer-nope"})
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is False
    assert r.json()["error"]