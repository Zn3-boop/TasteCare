"""Phase 4 regression tests — lock in prior bug fixes and data-surface guarantees.

  Phase 1A  build_multi_domain_itinerary has NO orphaned score_fit dead-code tail:
           the function returns a clean, deterministic itinerary contract.
  Phase 1B  /qloo routes have NO duplicate definitions (single /similarity and
           /taste-profile) — a past bug had two overrides, the later winning.
  Bug 3    low_sodium uses precise soy-seasoning keywords, so plain soy protein
           (tofu, edamame, soy milk) is never mis-flagged as salty.
  Phase 4B  fit_score is exposed on every TasteCare recommendation response
           (+ source label), and the 7-domain Taste Bridge order is stable.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

SERVER_ROOT = Path(__file__).resolve().parent.parent
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from app.main import app  # noqa: E402
from app.services.qloo.client import QlooClient, QlooConfig  # noqa: E402
from app.services.qloo.taste import (  # noqa: E402
    _BRIDGE_DOMAIN_ORDER,
    DOMAIN_TO_ENTITY_TYPE,
)
from app.services.qloo.tastecare import (  # noqa: E402
    _HEALTH_RULES,
    _annotate_health,
    build_multi_domain_itinerary,
    recommend_meals,
    score_fit,
)

client_http = TestClient(app)

QLOO_API_PATH = SERVER_ROOT / "app" / "api" / "qloo.py"
TASTECARE_PATH = SERVER_ROOT / "app" / "services" / "qloo" / "tastecare.py"

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _make_client(enabled: bool = True) -> QlooClient:
    return QlooClient(
        config=QlooConfig(
            api_key="test-key" if enabled else "",
            base_url="https://hackathon.api.qloo.com",
            timeout_seconds=10,
            max_retries=1,
        )
    )


# ═══════════════════════════════════════════════════════════════════════════
# Phase 1A — build_multi_domain_itinerary has no dead-code tail
# ═══════════════════════════════════════════════════════════════════════════


class TestBuildMultiDomainItineraryNoDeadcode:
    def test_source_has_no_orphaned_score_fit_tail(self):
        """The itinerary function must end with its own clean return, not the
        indentation-orphaned `scores` dict that used to append score_fit's tail."""
        src = _read(TASTECARE_PATH)
        fn_start = src.index("async def build_multi_domain_itinerary(")
        # build_multi_domain_itinerary is the LAST function in the module, so it
        # runs to EOF — there must be no trailing code after its own return.
        body = src[fn_start:]
        # The orphaned bug was: `total = len(order)` / `for eid, rank in order...`
        # appearing INSIDE build_multi_domain_itinerary. It must not be there.
        assert "total = len(order)" not in body
        assert "for eid, rank in order.items()" not in body
        # And the itinerary function must end with its own return statement.
        assert "return {" in body and "itinerary" in body[body.rindex("return {"):]
        # score_fit's body must contain its own return so scores are its tail.
        score_fit_src = src[src.index("async def score_fit("):src.index("\n\nasync def build_multi_domain_itinerary(")]
        assert "return scores" in score_fit_src

    def test_returns_clean_itinerary_contract(self):
        """Live-path itinerary returns exactly {itinerary, anchor_count, data_source}
        with well-formed nodes — no dead-code keys like `scores`/`order` leaking."""
        from asyncio import run

        c = _make_client(enabled=True)

        async def fake_search(client, query: str, **kw):
            return [{"name": query, "entity_id": f"e-{query}", "types": ["urn:entity:artist"]}]

        async def fake_insights(**kw):
            etype = kw["filter_type"]
            return {
                "results": {
                    "entities": [
                        {"entity_id": f"{etype}-1", "name": f"{etype} #1", "subtype": etype, "popularity": 0.9},
                        {"entity_id": f"{etype}-2", "name": f"{etype} #2", "subtype": etype, "popularity": 0.7},
                        {"entity_id": f"{etype}-3", "name": f"{etype} #3", "subtype": etype, "popularity": 0.5},
                    ]
                }
            }

        with patch("app.services.qloo.taste.search_cultural_entities", side_effect=fake_search), \
             patch.object(c, "insights", new_callable=AsyncMock, side_effect=fake_insights):
            result = run(build_multi_domain_itinerary(
                c,
                cultural_likes=["Jazz", "Frank Sinatra"],
                location=None,
                constraints={},
                take=2,
            ))

        assert set(result) == {"itinerary", "anchor_count", "data_source"}
        assert result["data_source"] == "live"
        assert result["anchor_count"] == 2
        assert result["itinerary"]
        for node in result["itinerary"]:
            assert set(node) == {"domain", "entity_id", "name", "fit", "popularity", "type"}
            assert node["fit"] > 0.0
            assert node["popularity"] is not None


# ═══════════════════════════════════════════════════════════════════════════
# Phase 1B — no duplicate /qloo routes
# ═══════════════════════════════════════════════════════════════════════════


class TestDuplicateRoutesRemoved:
    _ROUTES = ["similarity", "taste-profile"]

    def test_similarity_and_taste_profile_defined_once(self):
        src = _read(QLOO_API_PATH)
        for route in self._ROUTES:
            pattern = rf'@router\.post\("/{route}"'
            matches = re.findall(pattern, src)
            assert len(matches) == 1, f"route /{route} must be defined exactly once, found {len(matches)}"

    def test_no_route_path_defined_twice(self):
        src = _read(QLOO_API_PATH)
        for path in re.findall(r'@router\.(?:get|post|put|delete)\(([^)]+)\)', src):
            route_path = re.search(r'"/[^"]+"', path)
            if route_path:
                rp = route_path.group(0)
                assert len(re.findall(re.escape(rp), src)) == 1, f"duplicate route path {rp}"

    def test_app_registers_single_similarity_route(self):
        # `app.routes` wraps included routers in `_IncludedRouter` shims, so the
        # OpenAPI spec (which flattens every registered route) is the reliable
        # source of truth for "no duplicate definitions".
        spec = app.openapi()
        similarity = [p for p in spec["paths"] if p.endswith("/similarity")]
        taste_profile = [p for p in spec["paths"] if p.endswith("/taste-profile")]
        assert len(similarity) == 1, f"expected a single /similarity route, got {similarity}"
        assert len(taste_profile) == 1, f"expected a single /taste-profile route, got {taste_profile}"


# ═══════════════════════════════════════════════════════════════════════════
# Bug 3 — low_sodium soy precision (never flag plain soy protein)
# ═══════════════════════════════════════════════════════════════════════════


class TestLowSodiumSoyPrecision:
    def test_bare_soy_ingredient_products_are_not_salty(self):
        for name in [
            "Steamed Tofu with Vegetables",
            "Mapo Tofu (mild)",
            "Edamame Starter",
            "Soy Milk Rice Bowl",
            "Silken Tofu Soup",
        ]:
            result = _annotate_health({"name": name, "tags": []}, ["low_sodium"])
            assert result["passes"] is True, f"plain soy protein should pass low_sodium: {name}"

    def test_soy_seasoning_still_flags(self):
        for name in [
            "Soy Sauce Glazed Ribs",
            "Soy-braised Pork",
            "Teriyaki Soy Marinated Salmon",
            "Dumplings in Soy Sauce",
        ]:
            result = _annotate_health({"name": name, "tags": []}, ["low_sodium"])
            assert result["passes"] is False, f"soy-sauce-heavy dish should fail low_sodium: {name}"

    def test_avoid_rules_do_not_include_bare_soy(self):
        for kw in _HEALTH_RULES["low_sodium"]["avoid"]:
            assert kw != "soy", "bare 'soy' must not appear in low_sodium avoid"

    def test_description_haystack_still_flags_soy_sauce(self):
        entity = {"name": "Mystery Dish", "tags": [], "description": "Contains smoked salmon with soy sauce"}
        result = _annotate_health(entity, ["low_sodium"])

# ═══════════════════════════════════════════════════════════════════════════
# Phase 4B — fit score is exposed on every response + 7-domain bridge coverage
# ═══════════════════════════════════════════════════════════════════════════


class TestFitScoreExposedInResponse:
    def test_recommend_meals_exposes_fit_and_fit_source(self):
        from asyncio import run

        c = _make_client(enabled=True)
        mock_search = [{"entity_id": "e1", "name": "Jazz", "domain": "music"}]
        restaurant = {
            "entity_id": "r1",
            "name": "Jazz Supper Club",
            "subtype": "urn:entity:place",
            "popularity": 0.8,
            "tags": [
                {"name": "Jazz bar", "tag_id": "urn:tag:category:place:jazz_bar"},
                {"name": "Restaurant", "value": "urn:tag:category:place:restaurant"},
            ],
            "properties": {},
        }
        mock_insights = {"results": {"entities": [restaurant]}}
        with patch("app.services.qloo.tastecare.search_cultural_entities", new_callable=AsyncMock, return_value=mock_search), \
             patch.object(c, "insights", new_callable=AsyncMock, return_value=mock_insights), \
             patch("app.services.qloo.tastecare.score_fit", new_callable=AsyncMock, return_value={"r1": 0.73}):
            result = run(recommend_meals(c, cultural_likes=["Jazz"], take=5))

        assert result["recommendations"]
        for rec in result["recommendations"]:
            assert "fit" in rec, "each TasteCare recommendation must expose fit_score"
            assert rec["fit"] == 0.73
            assert rec["fit_source"] == "qloo-affinity"

    def test_fit_falls_back_to_popularity_labeled_honestly(self):
        from asyncio import run

        c = _make_client(enabled=True)
        mock_search = [{"entity_id": "e1", "name": "Jazz", "domain": "music"}]
        restaurant = {
            "entity_id": "r1",
            "name": "Jazz Diner",
            "subtype": "urn:entity:place",
            "popularity": 0.61,
            "tags": [{"name": "Restaurant", "value": "urn:tag:category:place:restaurant"}],
            "properties": {},
        }
        mock_insights = {"results": {"entities": [restaurant]}}
        with patch("app.services.qloo.tastecare.search_cultural_entities", new_callable=AsyncMock, return_value=mock_search), \
             patch.object(c, "insights", new_callable=AsyncMock, return_value=mock_insights), \
             patch("app.services.qloo.tastecare.score_fit", new_callable=AsyncMock, return_value={}):
            result = run(recommend_meals(c, cultural_likes=["Jazz"], take=5))

        rec = result["recommendations"][0]
        assert rec["fit"] == 0.61
        assert rec["fit_source"] == "qloo-popularity"

    def test_score_fit_contract(self):
        """score_fit returns a per-candidate float scores dict (no dead-code keys)."""
        from asyncio import run

        class FakeInsights:
            def __init__(self, payload):
                self.payload = payload

            async def insights(self, **_):
                return self.payload

        payload = {
            "results": {
                "entities": [
                    {"entity_id": "a", "name": "A", "subtype": "urn:entity:place", "popularity": 0.9},
                    {"entity_id": "b", "name": "B", "subtype": "urn:entity:place", "popularity": 0.7},
                ]
            }
        }
        out = run(score_fit(FakeInsights(payload), ["sig"], ["a", "b"]))
        assert set(out) == {"a", "b"}
        assert all(0.05 <= v <= 1.0 for v in out.values())
        assert out["a"] > out["b"]


class TestSevenDomainBridgeOrder:
    def test_bridge_domain_order_covers_all_seven(self):
        expected = ["music", "dining", "film", "travel", "fashion", "podcast", "book"]
        assert _BRIDGE_DOMAIN_ORDER == expected
        assert len(_BRIDGE_DOMAIN_ORDER) == 7

    def test_every_bridge_domain_has_entity_type(self):
        for d in _BRIDGE_DOMAIN_ORDER:
            assert d in DOMAIN_TO_ENTITY_TYPE, f"missing DOMAIN_TO_ENTITY_TYPE for {d}"

    def test_itinerary_domain_queries_cover_podcast_and_book(self):
        src = _read(TASTECARE_PATH)
        itiner_body = src[src.index("async def build_multi_domain_itinerary("):]
        assert "urn:entity:podcast" in itiner_body
        assert "urn:entity:book" in itiner_body
        assert "urn:entity:destination" in itiner_body

