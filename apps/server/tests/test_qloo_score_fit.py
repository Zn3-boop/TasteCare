"""Unit tests for the real Qloo-backed cultural-fit scoring in tastecare.py.

This is a network-free test: we hand score_fit() a stub client whose
``insights`` returns a fixed Qloo payload, so we can pin the exact
affinity-mapping contract without a QLOO_API_KEY.
"""

import asyncio

from app.services.qloo.tastecare import score_fit


def run(awaitable):
    return asyncio.new_event_loop().run_until_complete(awaitable)


class _FakeQlooClient:
    """Minimal stand-in for QlooClient exposing only ``insights``."""

    def __init__(self, payload):
        self._payload = payload
        self.calls = []

    async def insights(self, **kwargs):
        self.calls.append(kwargs)
        return self._payload


def _ordered_payload(*entity_ids):
    return {"results": {"entities": [{"entity_id": eid, "name": eid} for eid in entity_ids]}}


def test_score_fit_ranks_top_match_highest():
    """Qloo returns the most culturally-aligned entity first, so it must score highest."""
    client = _FakeQlooClient(
        _ordered_payload("urn:entity:place:b", "urn:entity:place:a", "urn:entity:place:c")
    )
    out = run(score_fit(client, ["signal_1"], ["urn:entity:place:a", "urn:entity:place:b", "urn:entity:place:c"]))

    assert set(out) == {"urn:entity:place:b", "urn:entity:place:a", "urn:entity:place:c"}
    assert out["urn:entity:place:b"] > out["urn:entity:place:a"] > out["urn:entity:place:c"]
    assert all(0.0 < v <= 1.0 for v in out.values())


def test_score_fit_single_candidate_gets_top_score():
    client = _FakeQlooClient(_ordered_payload("urn:entity:place:only"))
    out = run(score_fit(client, ["signal"], ["urn:entity:place:only"]))
    assert out == {"urn:entity:place:only": 1.0}


def test_score_fit_empty_candidates_returns_empty_without_calling_api():
    client = _FakeQlooClient({})  # should never be queried
    assert run(score_fit(client, ["signal"], [])) == {}
    assert client.calls == []


def test_score_fit_passes_signal_and_results_entities_to_insights():
    client = _FakeQlooClient(_ordered_payload("urn:entity:place:x"))
    run(score_fit(client, ["sig_id"], ["urn:entity:place:x"]))
    assert client.calls[0]["signal_entities"] == ["sig_id"]
    assert client.calls[0]["results_entities"] == ["urn:entity:place:x"]


def test_score_fit_returns_empty_on_api_error():
    client = _FakeQlooClient({"error": "auth_failed"})
    assert run(score_fit(client, ["signal"], ["urn:entity:place:x"])) == {}