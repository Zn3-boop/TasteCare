from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from app.services.qloo.client import QlooClient, QlooConfig
from app.services.qloo.tastecare import (
    recommend_meals,
    _annotate_health,
    _build_constraint_labels,
    MEDICATION_DISCLAIMER,
)


@pytest.fixture
def client():
    config = QlooConfig(api_key="test-key", base_url="https://hackathon.api.qloo.com", timeout_seconds=10, max_retries=1)
    return QlooClient(config=config)


def test_build_constraint_labels():
    assert _build_constraint_labels({"low_sugar": True, "low_sodium": True, "soft_chewable": True}) == ["low_sugar", "low_sodium", "soft_chewable"]
    assert _build_constraint_labels({"low_sugar": False}) == []


def test_annotate_health_soft_food():
    # porridge + steamed => soft-friendly
    entity = {"name": "Congee House", "tags": ["porridge", "Chinese"], "description": ""}
    result = _annotate_health(entity, ["soft_chewable"])
    assert result["passes"] is True
    assert "Soft food friendly" in result["labels"]


def test_annotate_health_flags_sodium():
    entity = {"name": "Salt & Smoke BBQ", "tags": ["bbq", "smoked"], "description": ""}
    result = _annotate_health(entity, ["low_sodium"])
    assert result["passes"] is False
    assert result["warnings"]


def test_annotate_health_flags_sugar():
    entity = {"name": "Sweet Bakery", "tags": ["dessert", "bakery"], "description": ""}
    result = _annotate_health(entity, ["low_sugar"])
    assert result["passes"] is False


@pytest.mark.asyncio
async def test_recommend_meals_requires_preferences(client):
    result = await recommend_meals(client, cultural_likes=[], location="New York")
    assert result["error"] == "no_preferences"


@pytest.mark.asyncio
async def test_recommend_meals_resolves_and_calls_insights(client):
    mock_search = [
        {"entity_id": "e1", "name": "Woody Allen", "domain": "film"},
    ]
    mock_insights = {
        "success": True,
        "results": {
            "entities": [
                {"name": "Maccheroni", "entity_id": "p1", "subtype": "urn:entity:place", "popularity": 0.9,
                 "tags": [{"name": "Italian"}], "properties": {}},
                {"name": "Salt & Smoke BBQ", "entity_id": "p2", "subtype": "urn:entity:place", "popularity": 0.85,
                 "tags": [{"name": "BBQ"}, {"name": "smoked"}], "properties": {}},
            ]
        },
    }
    with patch("app.services.qloo.tastecare.search_cultural_entities", new_callable=AsyncMock, return_value=mock_search), \
         patch.object(client, "insights", new_callable=AsyncMock, return_value=mock_insights) as mock_ins:
        result = await recommend_meals(
            client,
            cultural_likes=["Woody Allen"],
            location="New York",
            constraints={"low_sodium": True, "low_sugar": True},
            take=12,
        )
    assert result["source"] == "qloo"
    assert len(result["recommendations"]) == 2
    # healthy candidate passes, salty one fails
    by_name = {r["name"]: r for r in result["recommendations"]}
    assert by_name["Maccheroni"]["health"]["passes"] is True
    assert by_name["Salt & Smoke BBQ"]["health"]["passes"] is False
    # structured screening bucket derived from the health check (no recompute)
    assert by_name["Maccheroni"]["screening"] == "pass"
    assert by_name["Salt & Smoke BBQ"]["screening"] == "review"
    # sorted: passing candidate first
    assert result["recommendations"][0]["name"] == "Maccheroni"
    # insights called with place type + age signal + location
    # score_fit also calls insights (without location_query), so check call_args_list
    first_call_kwargs = mock_ins.call_args_list[0].kwargs
    assert first_call_kwargs["filter_type"] == "urn:entity:place"
    assert first_call_kwargs["location_query"] == "New York"
    assert first_call_kwargs["demographics_age"] == "55_and_older"
    assert MEDICATION_DISCLAIMER in result["disclaimer"]


def test_annotate_medication_flags_interaction():
    from app.services.qloo.tastecare import _annotate_medication
    flagged = {"name": "Grapefruit Brasserie", "tags": ["French", "citrus"]}
    result = _annotate_medication(flagged, True)
    assert result["passes"] is False
    assert result["warnings"]


def test_annotate_medication_clean_when_toggle_on():
    from app.services.qloo.tastecare import _annotate_medication
    clean = {"name": "Risotto House", "tags": ["Italian"]}
    result = _annotate_medication(clean, True)
    assert result["passes"] is True
    assert "Medication-screened" in result["labels"]


@pytest.mark.asyncio
async def test_recommend_meals_medication_aware_changes_results(client):
    mock_search = [{"entity_id": "e1", "name": "Frank Sinatra", "domain": "music"}]
    mock_insights = {
        "success": True,
        "results": {
            "entities": [
                {"name": "Grapefruit Grill", "entity_id": "p1", "subtype": "urn:entity:place", "popularity": 0.8,
                 "tags": [{"name": "citrus"}], "properties": {}},
                {"name": "Risotto House", "entity_id": "p2", "subtype": "urn:entity:place", "popularity": 0.7,
                 "tags": [{"name": "Italian"}], "properties": {}},
            ]
        },
    }
    with patch("app.services.qloo.tastecare.search_cultural_entities", new_callable=AsyncMock, return_value=mock_search), \
         patch.object(client, "insights", new_callable=AsyncMock, return_value=mock_insights):
        result = await recommend_meals(client, cultural_likes=["Frank Sinatra"], constraints={"medications": True}, take=10)
    assert "medications" in result["active_constraints"]
    by_name = {r["name"]: r for r in result["recommendations"]}
    assert by_name["Grapefruit Grill"]["health"]["passes"] is False
    assert by_name["Risotto House"]["health"]["passes"] is True
    # screening mirrors the raw health check for the medication path too
    assert by_name["Grapefruit Grill"]["screening"] == "review"
    assert by_name["Risotto House"]["screening"] == "pass"
    # flagged dish sinks below the clean dish when medication-aware is on
    assert result["recommendations"][0]["name"] == "Risotto House"


@pytest.mark.asyncio
async def test_recommend_meals_returns_error_when_insights_fail(client):
    mock_search = [{"entity_id": "e1", "name": "Radiohead", "domain": "music"}]
    mock_insights = {"error": "auth_failed", "detail": "status=401"}
    with patch("app.services.qloo.tastecare.search_cultural_entities", new_callable=AsyncMock, return_value=mock_search), \
         patch.object(client, "insights", new_callable=AsyncMock, return_value=mock_insights):
        result = await recommend_meals(client, cultural_likes=["Radiohead"], location="New York")
    assert result["error"] == "auth_failed"
    assert result["recommendations"] == []