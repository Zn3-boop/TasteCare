"""Tests for the TasteCare ablation comparison (variant A vs variant B).

Network-free by design: every test drives `run_ablation_comparison` with a
client stub whose `enabled` flag picks the preview/rule paths (or a live-mock
for the live path). The real Qloo smoke lives in
scripts/qloo_ablation_smoke.py and is NOT part of the pytest suite.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

SERVER_ROOT = Path(__file__).resolve().parent.parent
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from app.services.eval import ablation as abl  # noqa: E402
from app.services.qloo.tastecare import _is_dining_place  # noqa: E402

from app.services.eval.ablation import (  # noqa: E402
    _DEMO_CANDIDATES,
    _DEMO_CASES,
    _candidate_pool,
    _sort_by_health_then_fit,
    _to_variant_result,
    _variant_a,
    run_ablation_comparison,
)


def _disabled_client():
    """Client stub with Qloo disabled -> preview/rule paths."""
    stub = AsyncMock()
    stub.enabled = False
    return stub


def _enabled_client(payload):
    """Client stub with Qloo enabled; search/insights return fixed payloads."""
    stub = AsyncMock()
    stub.enabled = True

    async def fake_search(query, **kw):
        return {"success": True, "results": {"entities": [{"name": query, "entity_id": "e1", "types": ["urn:entity:place"]}]}}

    async def fake_insights(**kw):
        return payload

    stub.search = fake_search
    stub.insights = fake_insights
    return stub


# ===================== service layer =====================


class TestCandidatePool:
    def test_annotates_every_candidate_with_health(self):
        pool = _candidate_pool(["low_sodium", "soft_chewable"])
        assert len(pool) == len(_DEMO_CANDIDATES)
        for c in pool:
            assert "health" in c
            assert "passes" in c["health"]
            assert "labels" in c["health"]
            assert c["fit_source"] == "rules"

    def test_bbq_flagged_for_sodium(self):
        pool = _candidate_pool(["low_sodium"])
        bbq = next(c for c in pool if c["name"] == "Salt & Smoke BBQ")
        assert bbq["health"]["passes"] is False

    def test_congee_passes_soft_and_light(self):
        pool = _candidate_pool(["soft_chewable", "low_sodium"])
        congee = next(c for c in pool if c["name"] == "Jiangnan Congee House")
        assert congee["health"]["passes"] is True

    def test_bakery_flagged_for_sugar(self):
        pool = _candidate_pool(["low_sugar"])
        bakery = next(c for c in pool if c["name"] == "Sweet Bakery")
        assert bakery["health"]["passes"] is False


class TestSort:
    def test_passing_first_then_fit(self):
        candidates = [
            {"name": "low-fit pass", "health": {"passes": True}, "fit": 0.1},
            {"name": "high-fit fail", "health": {"passes": False}, "fit": 0.99},
            {"name": "high-fit pass", "health": {"passes": True}, "fit": 0.9},
        ]
        ordered = _sort_by_health_then_fit(candidates)
        assert ordered[0]["name"] == "high-fit pass"
        assert ordered[1]["name"] == "low-fit pass"
        assert ordered[2]["name"] == "high-fit fail"


class TestToVariantResult:
    def test_contract_fields_present(self):
        recs = [
            {
                "name": "Congee House",
                "health": {"passes": True, "labels": ["低钠倾向"], "warnings": []},
            },
            {
                "name": "BBQ",
                "health": {"passes": False, "labels": [], "warnings": ["可能高钠"]},
            },
        ]
        out = _to_variant_result(recs, "live")
        assert out["top_pick"] == "Congee House"
        assert out["has_cultural_match"] is True
        assert out["cultural_grounding"] == "live"
        assert out["data_source"] == "live"
        assert len(out["rationale"]) == 2
        first = out["rationale"][0]
        assert first["name"] == "Congee House"
        assert first["passes"] is True
        assert first["safety_validation"] == "低钠倾向"
        assert "cultural_match" in first

    def test_empty_recs_no_top_pick(self):
        out = _to_variant_result([], "preview")
        assert out["top_pick"] is None
        assert out["has_cultural_match"] is False
        assert out["rationale"] == []


class TestVariantA:
    def test_rules_never_calls_qloo(self):
        case = _DEMO_CASES[1]  # low_sodium + soft_chewable + low_sugar
        out = _variant_a(case)
        assert out["data_source"] == "rules"
        assert out["cultural_grounding"] == "rules"
        # all three constraints: congee (passes) must be top, BBQ + bakery flagged
        names = [r["name"] for r in out["rationale"]]
        assert out["top_pick"] == "Jiangnan Congee House"
        assert "Salt & Smoke BBQ" in names
        assert "Sweet Bakery" in names
        bbq = next(r for r in out["rationale"] if r["name"] == "Salt & Smoke BBQ")
        bakery = next(r for r in out["rationale"] if r["name"] == "Sweet Bakery")
        assert bbq["passes"] is False
        assert bakery["passes"] is False
        # every rationale has a safety_validation string
        assert all(r["safety_validation"] for r in out["rationale"])
class TestVariantB:
    @pytest.mark.asyncio
    async def test_preview_when_disabled(self):
        out = await abl._variant_b(_disabled_client(), _DEMO_CASES[1])
        assert out["data_source"] == "preview"
        assert out["top_pick"] == "Jiangnan Congee House"
        assert len(out["rationale"]) == len(_DEMO_CANDIDATES)

    @pytest.mark.asyncio
    async def test_live_when_enabled(self):
        payload = {
            "success": True,
            "results": {
                "entities": [
                    {"name": "Da Mario", "entity_id": "p1", "subtype": "urn:entity:place", "popularity": 0.8,
                     "tags": [{"name": "Italian"}], "properties": {}},
                ]
            },
        }
        out = await abl._variant_b(_enabled_client(payload), _DEMO_CASES[0])
        assert out["data_source"] == "live"
        assert out["top_pick"] == "Da Mario"
        assert out["cultural_grounding"] == "live"


class TestRunComparison:
    @pytest.mark.asyncio
    async def test_preview_mode_full_contract(self):
        result = await run_ablation_comparison(_disabled_client())
        assert result["data_source"] == "preview"
        assert len(result["comparison"]) == len(_DEMO_CASES)
        assert "timestamp" in result
        assert result["cases"] == _DEMO_CASES
        for row in result["comparison"]:
            assert row["case"] == row["case"]
            assert row["variant_a"]["data_source"] == "rules"
            assert row["variant_b"]["data_source"] == "preview"

    @pytest.mark.asyncio
    async def test_live_mode_uses_recommend_meals(self):
        payload = {
            "success": True,
            "results": {
                "entities": [
                    {"name": "Da Mario", "entity_id": "p1", "subtype": "urn:entity:place", "popularity": 0.8,
                     "tags": [{"name": "Italian"}], "properties": {}},
                ]
            },
        }
        stub = _enabled_client(payload)
        with patch("app.services.eval.ablation.recommend_meals", new_callable=AsyncMock) as mock_rm:
            mock_rm.return_value = {
                "recommendations": [
                    {"name": "Da Mario", "health": {"passes": True, "labels": ["低钠倾向"], "warnings": []}},
                ],
                "error": None,
                "source": "qloo",
            }
            result = await run_ablation_comparison(stub)
        assert result["data_source"] == "live"
        assert mock_rm.call_count == len(_DEMO_CASES)
        for row in result["comparison"]:
            assert row["variant_b"]["data_source"] == "live"

    @pytest.mark.asyncio
    async def test_live_error_falls_back_to_preview(self):
        payload = {"error": "auth_failed"}
        stub = _enabled_client(payload)
        result = await run_ablation_comparison(stub)
        # recommend_meals returns error -> variant_b falls back to preview pool
        for row in result["comparison"]:
            assert row["variant_b"]["data_source"] == "preview"


# ===================== API layer =====================


class TestAblationAPI:
    def test_comparison_endpoint_preview(self):
        from app.main import app

        client = TestClient(app)
        with patch("app.services.qloo.client.get_qloo_client", return_value=_disabled_client()):
            resp = client.post("/api/v1/ablation/comparison", json={})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["data_source"] == "preview"
        assert len(body["comparison"]) == len(_DEMO_CASES)
        for row in body["comparison"]:
            assert set(row) == {"case", "variant_a", "variant_b"}
            va, vb = row["variant_a"], row["variant_b"]
            for v in (va, vb):
                for key in ("top_pick", "has_cultural_match", "cultural_grounding", "data_source", "rationale"):
                    assert key in v

    def test_comparison_endpoint_live(self):
        from app.main import app

        client = TestClient(app)
        payload = {
            "success": True,
            "results": {
                "entities": [
                    {"name": "Da Mario", "entity_id": "p1", "subtype": "urn:entity:place", "popularity": 0.8,
                     "tags": [{"name": "Italian"}], "properties": {}},
                ]
            },
        }
        stub = _enabled_client(payload)
        with patch("app.services.qloo.client.get_qloo_client", return_value=stub):
            resp = client.post("/api/v1/ablation/comparison", json={})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["data_source"] == "live"
        assert body["comparison"][0]["variant_b"]["data_source"] == "live"


# ===================== dining-place discrimination =====================
# Qloo `urn:entity:place` mixes restaurants with museums/parks/landmarks.
# `_is_dining_place` (tastecare.py) keeps only entities that carry dining-specific
# tag URNs, so `location_query="New York"` no longer surfaces Niagara Falls etc.


class TestIsDiningPlace:
    def test_restaurant_with_dining_urns_passes(self):
        entity = {
            "name": "The Modern",
            "tag_urns": [
                "urn:tag:category:place:restaurant",
                "urn:tag:genre:place:restaurant:american",
                "urn:tag:cuisine:qloo:seafood",
            ],
        }
        assert _is_dining_place(entity) is True

    def test_restaurant_with_specialty_dish_passes(self):
        entity = {
            "name": "Dim Sum Palace",
            "tag_urns": ["urn:tag:specialty_dish:place:dumpling"],
        }
        assert _is_dining_place(entity) is True

    def test_landmark_without_dining_urns_fails(self):
        # Real shape from the live API: Niagara Falls State Park carries only
        # view / amenities / nearby_attraction tag URNs — no dining signals.
        entity = {
            "name": "Niagara Falls State Park",
            "tag_urns": [
                "urn:tag:view:qloo:waterfall_view",
                "urn:tag:amenities:place:basketball_court",
                "urn:tag:nearby_attraction:qloo:cave_of_the_winds",
            ],
        }
        assert _is_dining_place(entity) is False

    def test_museum_without_dining_urns_fails(self):
        entity = {
            "name": "Museum of Modern Art",
            "tag_urns": [
                "urn:tag:activity_type:qloo:culture_arts",
                "urn:tag:category:place:museum",
            ],
        }
        assert _is_dining_place(entity) is False

    def test_preview_pool_with_no_urns_is_allowed(self):
        # Offline preview candidates carry no tag URNs; they must not be filtered.
        entity = {"name": "Jiangnan Congee House", "tag_urns": []}
        assert _is_dining_place(entity) is True

    def test_mixed_tags_with_one_dining_signal_passes(self):
        entity = {
            "name": "Cafe & Museum Shop",
            "tag_urns": [
                "urn:tag:view:qloo:garden_view",
                "urn:tag:dining_options:place:cafe",
            ],
        }
        assert _is_dining_place(entity) is True


class TestRecommendMealsFiltersNonDining:
    @pytest.mark.asyncio
    async def test_non_dining_places_are_dropped(self):
        from app.services.qloo.tastecare import recommend_meals

        # A payload mixing one real restaurant with two landmarks: only the
        # restaurant should survive dining discrimination.
        payload = {
            "success": True,
            "results": {
                "entities": [
                    {
                        "name": "The Modern",
                        "entity_id": "p-rest",
                        "subtype": "urn:entity:place",
                        "popularity": 0.9,
                        "tags": [
                            {"name": "Restaurant", "tag_id": "urn:tag:category:place:restaurant", "type": "urn:tag:category:place"},
                            {"name": "American", "tag_id": "urn:tag:genre:place:restaurant:american", "type": "urn:tag:genre:place"},
                        ],
                        "properties": {},
                    },
                    {
                        "name": "Niagara Falls State Park",
                        "entity_id": "p-park",
                        "subtype": "urn:entity:place",
                        "popularity": 0.95,
                        "tags": [
                            {"name": "Waterfall view", "tag_id": "urn:tag:view:qloo:waterfall_view", "type": "urn:tag:view:qloo"},
                        ],
                        "properties": {},
                    },
                    {
                        "name": "Museum of Modern Art",
                        "entity_id": "p-museum",
                        "subtype": "urn:entity:place",
                        "popularity": 0.8,
                        "tags": [
                            {"name": "Museum", "tag_id": "urn:tag:category:place:museum", "type": "urn:tag:category:place"},
                        ],
                        "properties": {},
                    },
                ]
            },
        }
        stub = _enabled_client(payload)
        result = await recommend_meals(
            stub,
            cultural_likes=["fine dining"],
            location="New York",
            take=5,
        )
        assert result.get("error") is None
        names = [r["name"] for r in result["recommendations"]]
        assert "The Modern" in names
        assert "Niagara Falls State Park" not in names
        assert "Museum of Modern Art" not in names
        assert result["filtered_non_dining"] == 2

    @pytest.mark.asyncio
    async def test_filtered_count_zero_when_all_dining(self):
        from app.services.qloo.tastecare import recommend_meals

        payload = {
            "success": True,
            "results": {
                "entities": [
                    {
                        "name": "Dim Sum Palace",
                        "entity_id": "p-ds",
                        "subtype": "urn:entity:place",
                        "popularity": 0.7,
                        "tags": [
                            {"name": "Dumpling", "tag_id": "urn:tag:specialty_dish:place:dumpling", "type": "urn:tag:specialty_dish:place"},
                        ],
                        "properties": {},
                    },
                ]
            },
        }
        stub = _enabled_client(payload)
        result = await recommend_meals(stub, cultural_likes=["dim sum"], take=5)
        assert result.get("error") is None
        assert len(result["recommendations"]) == 1
        assert result["filtered_non_dining"] == 0