from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from app.services.qloo.client import QlooClient, QlooConfig
from app.services.qloo.taste import (
    search_cultural_entities,
    get_taste_based_recommendations,
    get_cross_domain_discovery,
    build_cultural_context_for_llm,
    apply_taste_preferences,
    _normalize_entity,
)


@pytest.fixture
def client():
    config = QlooConfig(api_key="test-key", base_url="https://hackathon.api.qloo.com", timeout_seconds=10, max_retries=1)
    return QlooClient(config=config)


@pytest.fixture(autouse=True)
def _reset_feedback_pools():
    """Feedback pools are module-global; reset before/after every test so live-mode
    recommendation tests never inherit 👍/👎 state recorded by an earlier test."""
    from app.services.qloo import feedback as _fb
    _fb._feedback_records.clear()
    _fb._preview_pool_deltas.clear()
    _fb._liked_taste_names.clear()
    _fb._disliked_taste_names.clear()
    yield
    _fb._feedback_records.clear()
    _fb._preview_pool_deltas.clear()
    _fb._liked_taste_names.clear()
    _fb._disliked_taste_names.clear()


@pytest.mark.asyncio
async def test_search_cultural_entities(client):
    mock_result = {
        "success": True,
        "results": {
            "entities": [
                {"name": "Radiohead", "entity_id": "e1", "subtype": "urn:entity:artist"},
            ]
        },
    }
    with patch.object(client, "search", new_callable=AsyncMock, return_value=mock_result):
        results = await search_cultural_entities(client, "Radiohead", domain="music")
        assert len(results) == 1
        assert results[0]["name"] == "Radiohead"
        assert results[0]["entity_id"] == "e1"
        assert results[0]["domain"] == "music"


@pytest.mark.asyncio
async def test_search_normalizes_types_only_entities(client):
    """Qloo /search returns entities with ONLY `types: [URN]` — no `subtype`. The
    normalizer must still resolve the entity-type URN + domain (the bug that used to
    silently blank the domain for every /search entity)."""
    mock_result = {
        "success": True,
        "results": {
            "entities": [
                {
                    "name": "My Neighbor Totoro",
                    "entity_id": "totoro-uuid",
                    "types": ["urn:entity:movie"],
                },
            ]
        },
    }
    with patch.object(client, "search", new_callable=AsyncMock, return_value=mock_result) as mock_search:
        results = await search_cultural_entities(client, "Totoro", domain="film")
        assert len(results) == 1
        assert results[0]["entity_id"] == "totoro-uuid"
        assert results[0]["type"] == "urn:entity:movie"
        assert results[0]["domain"] == "film"
        # /search must be called (not /v2/insights), with types mapped for film.
        _args, _kwargs = mock_search.call_args
        assert _kwargs.get("entity_types") == ["urn:entity:movie"]


def test_normalize_entity_types_only_maps_domain():
    """Direct _normalize_entity check for the /search-only shape (types[] without subtype)."""
    raw = {"name": "Infinite Jest", "entity_id": "u-1", "types": ["urn:entity:book"]}
    norm = _normalize_entity(raw)
    assert norm["type"] == "urn:entity:book"
    assert norm["domain"] == "book"


def test_normalize_entity_dining_domain_types_only():
    """dining /search entities (types: [urn:entity:place]) map to dining, not blank."""
    raw = {"name": "Blue Hill", "entity_id": "bh-1", "types": ["urn:entity:place"]}
    norm = _normalize_entity(raw)
    assert norm["type"] == "urn:entity:place"
    assert norm["domain"] == "dining"


@pytest.mark.asyncio
async def test_search_cultural_entities_error(client):
    with patch.object(client, "search", new_callable=AsyncMock, return_value={"error": "failed"}):
        results = await search_cultural_entities(client, "test")
        assert results == []


@pytest.mark.asyncio
async def test_get_taste_based_recommendations(client):
    mock_result = {
        "success": True,
        "results": {
            "entities": [
                {"name": "Muse", "entity_id": "e2", "subtype": "urn:entity:artist", "popularity": 0.9},
            ]
        },
    }
    with patch.object(client, "insights", new_callable=AsyncMock, return_value=mock_result):
        result = await get_taste_based_recommendations(client, ["e1"], target_domain="music")
        assert len(result["recommendations"]) == 1
        assert result["source"] == "qloo"
        assert result["recommendations"][0]["name"] == "Muse"


@pytest.mark.asyncio
async def test_get_taste_based_recommendations_no_seeds(client):
    result = await get_taste_based_recommendations(client, [])
    assert result["recommendations"] == []
    assert result["error"] == "no_seed_entities"


@pytest.mark.asyncio
async def test_apply_taste_preferences_injects_liked_filters_disliked(client):
    """Live feedback overlay end-to-end:
    - 👍 'Radiohead' resolves to UUID e1 and is PREPENDED to signal.interests.entities
    - 👎 'Muse' resolves to UUID e2 and is FILTERED OUT of the returned results
    """
    from app.services.qloo import feedback as _fb
    _fb.record_feedback("like-1", "up", ["Radiohead"])
    _fb.record_feedback("dislike-1", "down", ["Muse"])

    def fake_search(query, **kw):
        if "Radiohead" in query:
            return {"success": True, "results": {"entities": [{"name": "Radiohead", "entity_id": "e1", "types": ["urn:entity:artist"]}]}}
        return {"success": True, "results": {"entities": [{"name": "Muse", "entity_id": "e2", "types": ["urn:entity:artist"]}]}}

    mock_insights = {
        "success": True,
        "results": {
            "entities": [
                {"name": "Muse", "entity_id": "e2", "subtype": "urn:entity:artist"},
                {"name": "Coldplay", "entity_id": "e3", "subtype": "urn:entity:artist"},
            ]
        },
    }
    with patch.object(client, "search", new_callable=AsyncMock, side_effect=fake_search) as mock_search:
        with patch.object(client, "insights", new_callable=AsyncMock, return_value=mock_insights) as mock_insights_call:
            payload = await apply_taste_preferences(
                client, signal_entities=["seed-1"], take=4, filter_type="urn:entity:artist"
            )

    # 👍 UUID prepended (highest weight), before the caller-provided seeds.
    signals = mock_insights_call.call_args.kwargs["signal_entities"]
    assert signals[0] == "e1"
    assert "seed-1" in signals

    # 👎 excluded from results; remaining entities are kept.
    remaining = [e["entity_id"] for e in payload["results"]["entities"]]
    assert "e2" not in remaining
    assert "e3" in remaining
    assert payload["results"]["preferences_applied"]["disliked_removed"] == 1

    # Both pools were resolved via /search (types-only UUID resolution).
    assert mock_search.call_count == 2


@pytest.mark.asyncio
async def test_get_taste_based_recommendations_live_applies_overlay(client):
    """Live enabled client + non-empty pools: recommendations are re-weighted by the
    local 👍 overlay and 👎 entities never appear."""
    from app.services.qloo import feedback as _fb
    _fb.record_feedback("like-2", "up", ["Radiohead"])

    def fake_search(query, **kw):
        return {"success": True, "results": {"entities": [{"name": "Radiohead", "entity_id": "e1", "types": ["urn:entity:artist"]}]}}

    mock_insights = {
        "success": True,
        "results": {
            "entities": [
                {"name": "Radiohead", "entity_id": "e1", "subtype": "urn:entity:artist"},
                {"name": "Muse", "entity_id": "e2", "subtype": "urn:entity:artist"},
            ]
        },
    }
    with patch.object(client, "search", new_callable=AsyncMock, side_effect=fake_search):
        with patch.object(client, "insights", new_callable=AsyncMock, return_value=mock_insights) as mock_ins:
            result = await get_taste_based_recommendations(client, ["seed-1"], target_domain="music", limit=3)

    assert result["source"] == "qloo"
    names = [r["name"] for r in result["recommendations"]]
    assert "Radiohead" in names
    assert "Muse" in names
    # liked feed went through the overlay: signal list starts with the liked UUID
    sig = mock_ins.call_args.kwargs["signal_entities"]
    assert sig[0] == "e1"


@pytest.mark.asyncio
async def test_get_cross_domain_discovery(client):
    mock_rec = {"recommendations": [{"name": "Muse", "entity_id": "e2"}], "source": "qloo"}
    with patch("app.services.qloo.taste.get_taste_based_recommendations", new_callable=AsyncMock, return_value=mock_rec):
        result = await get_cross_domain_discovery(client, ["e1"], domains=["music", "film"], per_domain_limit=3)
        assert "music" in result
        assert "film" in result


@pytest.mark.asyncio
async def test_build_cultural_context_for_llm_disabled():
    config = QlooConfig(api_key="", base_url="https://hackathon.api.qloo.com", timeout_seconds=10, max_retries=1)
    client = QlooClient(config=config)
    result = await build_cultural_context_for_llm(client, ["Radiohead"])
    assert result == ""


@pytest.mark.asyncio
async def test_build_cultural_context_for_llm(client):
    mock_search = [{"entity_id": "e1", "name": "Radiohead", "domain": "music"}]
    mock_rec = {"recommendations": [{"entity_id": "e2", "name": "Muse", "type": "urn:entity:artist", "domain": "music"}], "source": "qloo"}
    with patch("app.services.qloo.taste.search_cultural_entities", new_callable=AsyncMock, return_value=mock_search), \
         patch("app.services.qloo.taste.get_taste_based_recommendations", new_callable=AsyncMock, return_value=mock_rec):
        result = await build_cultural_context_for_llm(client, ["Radiohead"], target_domain="music")
        assert "Qloo Cultural Intelligence" in result
        assert "Muse" in result
