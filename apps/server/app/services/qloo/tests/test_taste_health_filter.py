from __future__ import annotations

import pytest

from app.services.graph.nodes import (
    taste_health_filter_node,
    route_after_taste_health_filter,
    route_after_qloo,
    answer_generation_node,
)

def _make_state(
    recommendations=None,
    health_constraints=None,
    taste_entities=None,
    taste_data_source="preview",
    last_error=None,
):
    return {
        "qloo_recommendations": recommendations or [],
        "health_constraints": health_constraints or {},
        "health_constraint_labels": [],
        "taste_entities": taste_entities or [],
        "taste_data_source": taste_data_source,
        "last_error": last_error,
    }

class TestTasteHealthFilterNode:
    @pytest.mark.asyncio
    async def test_empty_recommendations_returns_empty(self):
        state = _make_state()
        result = await taste_health_filter_node(state)
        assert result["filtered_recommendations"] == []
        assert result["filter_summary"]["total"] == 0

    @pytest.mark.asyncio
    async def test_no_constraints_all_pass(self):
        recs = [
            {"name": "Restaurant A", "tags": ["Italian"], "popularity": 0.9},
            {"name": "Restaurant B", "tags": ["Chinese"], "popularity": 0.8},
        ]
        state = _make_state(recommendations=recs)
        result = await taste_health_filter_node(state)
        assert len(result["filtered_recommendations"]) == 2
        assert result["filter_summary"]["passed"] == 2
        assert result["filter_summary"]["flagged"] == 0

    @pytest.mark.asyncio
    async def test_low_sodium_flags_salty(self):
        recs = [
            {"name": "Maccheroni", "tags": ["Italian"], "popularity": 0.9},
            {"name": "Salt & Smoke BBQ", "tags": ["BBQ", "smoked"], "popularity": 0.85},
        ]
        constraints = {"low_sodium": True}
        state = _make_state(recommendations=recs, health_constraints=constraints)
        result = await taste_health_filter_node(state)
        filtered = result["filtered_recommendations"]
        by_name = {r["name"]: r for r in filtered}
        assert by_name["Maccheroni"]["health"]["passes"] is True
        assert by_name["Salt & Smoke BBQ"]["health"]["passes"] is False
        assert filtered[0]["name"] == "Maccheroni"
        assert result["filter_summary"]["active_labels"] == ["low_sodium"]

    @pytest.mark.asyncio
    async def test_low_sugar_flags_dessert(self):
        recs = [
            {"name": "Sweet Bakery", "tags": ["dessert", "bakery"], "popularity": 0.9},
            {"name": "Risotto House", "tags": ["Italian"], "popularity": 0.7},
        ]
        constraints = {"low_sugar": True}
        state = _make_state(recommendations=recs, health_constraints=constraints)
        result = await taste_health_filter_node(state)
        filtered = result["filtered_recommendations"]
        by_name = {r["name"]: r for r in filtered}
        assert by_name["Sweet Bakery"]["health"]["passes"] is False
        assert by_name["Risotto House"]["health"]["passes"] is True

    @pytest.mark.asyncio
    async def test_soft_chewable_prefers_soft_food(self):
        recs = [
            {"name": "Congee House", "tags": ["porridge", "Chinese"], "popularity": 0.8},
            {"name": "Crunchy Nuts Bar", "tags": ["nuts", "crunchy"], "popularity": 0.9},
        ]
        constraints = {"soft_chewable": True}
        state = _make_state(recommendations=recs, health_constraints=constraints)
        result = await taste_health_filter_node(state)
        filtered = result["filtered_recommendations"]
        by_name = {r["name"]: r for r in filtered}
        assert by_name["Congee House"]["health"]["passes"] is True
        assert by_name["Crunchy Nuts Bar"]["health"]["passes"] is False

    @pytest.mark.asyncio
    async def test_medication_aware_flags_interaction(self):
        recs = [
            {"name": "Grapefruit Grill", "tags": ["citrus"], "popularity": 0.8},
            {"name": "Risotto House", "tags": ["Italian"], "popularity": 0.7},
        ]
        constraints = {"medications": ["antihypertensive"]}
        state = _make_state(recommendations=recs, health_constraints=constraints)
        result = await taste_health_filter_node(state)
        filtered = result["filtered_recommendations"]
        by_name = {r["name"]: r for r in filtered}
        assert by_name["Grapefruit Grill"]["health"]["passes"] is False
        assert by_name["Risotto House"]["health"]["passes"] is True
        assert result["filter_summary"]["medication_aware"] is True

    @pytest.mark.asyncio
    async def test_taste_anchors_in_summary(self):
        recs = [{"name": "R1", "tags": [], "popularity": 0.5}]
        taste_entities = [
            {"name": "Jazz", "entity_id": "e1"},
            {"name": "Italian dining", "entity_id": "e2"},
        ]
        state = _make_state(recommendations=recs, taste_entities=taste_entities)
        result = await taste_health_filter_node(state)
        assert result["filter_summary"]["taste_anchors"] == ["Jazz", "Italian dining"]

    @pytest.mark.asyncio
    async def test_combined_constraints(self):
        recs = [
            {"name": "Healthy Soup", "tags": ["soup", "fresh"], "popularity": 0.7},
            {"name": "Salty BBQ", "tags": ["smoked", "salty"], "popularity": 0.9},
            {"name": "Sweet Dessert", "tags": ["dessert", "bakery"], "popularity": 0.8},
        ]
        constraints = {"low_sodium": True, "low_sugar": True, "soft_chewable": True}
        state = _make_state(recommendations=recs, health_constraints=constraints)
        result = await taste_health_filter_node(state)
        filtered = result["filtered_recommendations"]
        by_name = {r["name"]: r for r in filtered}
        assert by_name["Healthy Soup"]["health"]["passes"] is True
        assert by_name["Salty BBQ"]["health"]["passes"] is False
        assert by_name["Sweet Dessert"]["health"]["passes"] is False
        assert filtered[0]["name"] == "Healthy Soup"
        assert result["filter_summary"]["active_labels"] == ["low_sugar", "low_sodium", "soft_chewable"]

class TestRouteAfterTasteHealthFilter:
    def test_routes_to_planning_on_success(self):
        state = _make_state()
        assert route_after_taste_health_filter(state) == "answer_generation_node"

    def test_routes_to_error_on_failure(self):
        state = _make_state(last_error="something broke")
        assert route_after_taste_health_filter(state) == "error_fallback_node"

class TestRouteAfterQlooUpdated:
    def test_routes_to_filter_node_on_success(self):
        state = _make_state()
        assert route_after_qloo(state) == "taste_health_filter_node"

    def test_routes_to_error_on_failure(self):
        state = _make_state(last_error="qloo failed")
        assert route_after_qloo(state) == "error_fallback_node"

class TestAnswerGenerationNode:
    @pytest.mark.asyncio
    async def test_builds_two_part_rationale_and_final_answer(self):
        filtered = [
            {
                "name": "Bibimbap",
                "tags": ["korean", "rice"],
                "popularity": 0.95,
                "health": {"passes": True, "labels": [], "warnings": []},
            }
        ]
        state = _make_state(
            recommendations=filtered,
            taste_entities=["Bibimbap"],
        )
        state["filtered_recommendations"] = filtered
        state["filter_summary"] = {"active_labels": [], "skipped": 0, "passed": 1}
        result = await answer_generation_node(state)
        assert result["final_answer"]
        ag = result["answer_generation"]
        assert ag["rationale"]
        first = ag["rationale"][0]
        assert first["name"] == "Bibimbap"
        assert first["passes"] is True
        assert "cultural_match" in first
        assert "safety_validation" in first