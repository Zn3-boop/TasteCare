"""Feedback loop tests: /chat/feedback endpoint + in-memory feedback store.

Covers the feedback loop without depending on deleted tools/executor or tools/schema modules.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

SERVER_ROOT = Path(__file__).resolve().parent.parent
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from app.main import app  # noqa: E402
from app.services.qloo import feedback as feedback_store  # noqa: E402

client = TestClient(app)


def _mock_qloo_disabled():
    mock_client = AsyncMock()
    mock_client.enabled = False
    return mock_client


def _mock_qloo_enabled():
    mock_client = AsyncMock()
    mock_client.enabled = True
    return mock_client


def test_feedback_endpoint_preview_records():
    feedback_store._feedback_records.clear()
    with patch(
        "app.services.qloo.client.get_qloo_client", return_value=_mock_qloo_disabled()
    ):
        resp = client.post(
            "/chat/feedback",
            json={
                "message_id": "msg-1",
                "thumb": "up",
                "taste_entities": ["Jiangnan light braised cuisine", "Low-sodium clear broth soups"],
            },
        )

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["ok"] is True
    assert payload["recorded"] is True
    assert payload["data_source"] == "preview"
    assert payload["qloo_enabled"] is False
    assert payload["thumb"] == "up"
    assert payload["message_id"] == "msg-1"
    assert "preview" in (payload["note"] or "").lower()

    records = feedback_store.get_feedback_records()
    assert "msg-1" in records
    assert records["msg-1"]["thumb"] == "up"
    assert len(records["msg-1"]["taste_entities"]) == 2


def test_feedback_endpoint_live_records_overlay():
    feedback_store._feedback_records.clear()
    feedback_store._liked_taste_names.clear()
    feedback_store._disliked_taste_names.clear()
    with patch(
        "app.services.qloo.client.get_qloo_client", return_value=_mock_qloo_enabled()
    ):
        resp = client.post(
            "/chat/feedback",
            json={
                "message_id": "msg-live-1",
                "thumb": "up",
                "taste_entities": ["Radiohead"],
            },
        )

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["ok"] is True
    assert payload["data_source"] == "live"
    assert payload["qloo_enabled"] is True
    assert payload["recorded"] is True
    assert payload["liked_taste_names"] == ["Radiohead"]
    assert payload["disliked_taste_names"] == []

    assert feedback_store.get_liked_taste_names()["Radiohead"] == 1.0


def test_feedback_endpoint_live_down_up_moves_between_pools():
    feedback_store._feedback_records.clear()
    feedback_store._liked_taste_names.clear()
    feedback_store._disliked_taste_names.clear()
    with patch(
        "app.services.qloo.client.get_qloo_client", return_value=_mock_qloo_enabled()
    ):
        client.post("/chat/feedback", json={"message_id": "m1", "thumb": "down", "taste_entities": ["Muse"]})
        resp = client.post("/chat/feedback", json={"message_id": "m2", "thumb": "up", "taste_entities": ["Muse"]})

    payload = resp.json()
    assert payload["liked_taste_names"] == ["Muse"]
    assert payload["disliked_taste_names"] == []
    assert feedback_store.get_liked_taste_names().get("Muse") == 1.0
    assert "Muse" not in feedback_store.get_disliked_taste_names()


def test_feedback_endpoint_bad_thumb_rejected():
    resp = client.post("/chat/feedback", json={"message_id": "m", "thumb": "meh"})
    assert resp.status_code == 422


def test_feedback_store_roundtrip_deltas():
    feedback_store._feedback_records.clear()
    feedback_store._preview_pool_deltas.clear()

    feedback_store.record_feedback("m-up", "up", ["Jiangnan light braised cuisine"])
    feedback_store.record_feedback("m-down", "down", ["Jiangnan light braised cuisine"])

    deltas = feedback_store.get_preview_pool_deltas()