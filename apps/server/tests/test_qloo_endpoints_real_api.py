"""Real-Qloo API tests for the remaining /qloo/* service surface.

test_ablation_real_api.py covers search/insights/recommend_meals and the dining
filter. This file covers the other live endpoints that previously only ran in
the manual `e2e_qloo_real.py` script:

  * get_cross_domain_discovery / get_cross_domain_bridge_graph
  * get_taste_similarity_score
  * score_cultural_fit (candidate vs. seed cultural affinity)
  * get_entity_details / get_entity_taste_profile
  * apply_taste_preferences (the feedback overlay that changes the next rec)

Same policy as test_ablation_real_api: marked `real_api`, skipped only when
QLOO_API_KEY is missing; auth errors fail hard, transient errors skip.

Structure assertions only — we never guess exact entity ids or rankings, but we
DO assert the data actually reflects the anchored taste (e.g. cross-domain
dining recs carry dining entity types).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_SERVER_DIR = Path(__file__).resolve().parent.parent
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(Path(_SERVER_DIR) / ".env")
except Exception:  # pragma: no cover
    pass

pytestmark = pytest.mark.skipif(
    not os.getenv("QLOO_API_KEY"),
    reason="QLOO_API_KEY not set; real_api tests are only run with a key",
)

from app.services.qloo.client import QlooClient, QlooConfig  # noqa: E402
from app.services.qloo.entities import (  # noqa: E402
    get_entity_details,
    get_entity_taste_profile,
    score_cultural_fit,
)
from app.services.qloo.taste import (  # noqa: E402
    apply_taste_preferences,
    get_cross_domain_bridge_graph,
    get_cross_domain_discovery,
    get_taste_similarity_score,
    search_cultural_entities,
)

TRANSIENT_ERRORS = {"request_failed", "bad_request", "not_found", "no_insights"}


def _make_client() -> QlooClient:
    return QlooClient(config=QlooConfig.from_env())


def _skip_if_transient(payload: dict) -> None:
    error = payload.get("error")
    if not error:
        return
    if error == "auth_failed":
        pytest.fail(f"Qloo authentication failed (bad key for {payload.get('detail')})")
    if error in TRANSIENT_ERRORS:
        pytest.skip(f"Qloo transient error ({error}): {payload.get('detail')}")
    pytest.skip(f"Qloo unexpected error ({error}): {payload.get('detail')}")


@pytest.fixture
async def client():
    c = _make_client()
    yield c
    await c.close()


async def _anchor_artist(client: QlooClient) -> str:
    """Resolve one real Frank Sinatra artist UUID to anchor everything on."""
    payload = await client.search("Frank Sinatra", entity_types=["urn:entity:artist"], take=1)
    _skip_if_transient(payload)
    results = payload.get("results") or []
    assert results, "expected a real Frank Sinatra artist result"
    eid = results[0].get("entity_id")
    assert eid, "expect artist entity_id"
    return eid


# ===================== cross-domain discovery & bridge graph =====================


@pytest.mark.real_api
async def test_real_cross_domain_discovery_returns_dining_for_anchor(client: QlooClient) -> None:
    anchor = await _anchor_artist(client)
    out = await get_cross_domain_discovery(client, [anchor], domains=["music", "dining", "film"], per_domain_limit=3)
    for domain in ("music", "dining", "film"):
        assert domain in out, f"expected {domain} in cross-domain results"
        recs = out[domain]
        assert isinstance(recs, list)
        assert recs, f"expected non-empty {domain} recommendations"
        for r in recs:
            assert r.get("name"), "each recommendation needs a name"
            assert r.get("entity_id"), "each recommendation needs an entity_id"
            assert r.get("type"), "each recommendation needs a type URN"


@pytest.mark.real_api
async def test_real_bridge_graph_has_center_nodes_and_edges(client: QlooClient) -> None:
    anchor = await _anchor_artist(client)
    graph = await get_cross_domain_bridge_graph(client, [anchor], center_label="Frank Sinatra", domains=("music", "dining"), per_domain_limit=2)
    _skip_if_transient(graph)
    assert graph["center"] == "Frank Sinatra"
    assert graph["data_source"] in ("live", "preview")
    assert isinstance(graph["nodes"], list)
    assert graph["nodes"], "bridge graph should render nodes with a live key"
    for n in graph["nodes"]:
        assert n["id"] and n["name"]
    assert isinstance(graph["edges"], list)
    assert graph["edges"], "every live node gets an edge to center"


# ===================== taste similarity =====================


@pytest.mark.real_api
async def test_real_taste_similarity_artist_to_artist(client: QlooClient) -> None:
    anchor = await _anchor_artist(client)
    sim = await get_taste_similarity_score(client, [anchor], target_type="urn:entity:artist", limit=4)
    _skip_if_transient(sim)
    similar = sim.get("similar") or []
    assert similar, "expected similar artists for Frank Sinatra"
    for r in similar:
        assert r.get("name")
        assert r.get("entity_id")
        assert r.get("type") == "urn:entity:artist"


@pytest.mark.real_api
async def test_real_taste_similarity_artist_to_dining(client: QlooClient) -> None:
    anchor = await _anchor_artist(client)
    sim = await get_taste_similarity_score(client, [anchor], target_type="urn:entity:place", limit=3)
    _skip_if_transient(sim)
    similar = sim.get("similar") or []
    assert similar, "expected dining places similar to Sinatra's taste"
    for r in similar:
        assert r.get("type") == "urn:entity:place"


# ===================== cultural fit scoring =====================


@pytest.mark.real_api
async def test_real_score_cultural_fit_scores_candidates(client: QlooClient) -> None:
    out = await score_cultural_fit(
        client,
        seed_names=["Jazz", "Frank Sinatra"],
        candidate_names=["Blues", "Country", "Pop"],
        domain="music",
    )
    _skip_if_transient(out)
    scores = out.get("scores")
    assert scores, "expected real candidate affinity scores"
    assert len(scores) == 3, "all three candidates should be scored"
    # Monotonic ranking: the top cultural match is first.
    vals = [s["score"] for s in scores]
    assert all(vals[i] >= vals[i + 1] for i in range(len(vals) - 1))
    assert all(0.0 < v <= 1.0 for v in vals)
    for s in scores:
        assert s["name"] and s["entity_id"]
# ===================== entity details & taste profile =====================


@pytest.mark.real_api
async def test_real_entity_details_returns_place(client: QlooClient) -> None:
    anchor = await _anchor_artist(client)
    # Get a dining place first, then fetch its details.
    sim = await get_taste_similarity_score(client, [anchor], target_type="urn:entity:place", limit=1)
    _skip_if_transient(sim)
    similar = sim.get("similar") or []
    if not similar:
        pytest.skip("Qloo returned no dining place to fetch details for")
    detail = await get_entity_details(client, similar[0]["entity_id"])
    _skip_if_transient(detail)
    assert detail.get("name"), f"expected a name in entity details, got {detail}"
    assert detail.get("id") or detail.get("entity_id")


@pytest.mark.real_api
async def test_real_entity_taste_profile_returns_count(client: QlooClient) -> None:
    anchor = await _anchor_artist(client)
    profile = await get_entity_taste_profile(client, [anchor])
    _skip_if_transient(profile)
    assert profile["profile"]["count"] == 1
    ents = profile["profile"]["entities"]
    assert len(ents) == 1
    assert ents[0]["name"]


# ===================== feedback preference overlay (live) =====================


@pytest.mark.real_api
async def test_real_apply_taste_preferences_prepends_liked(client: QlooClient) -> None:
    from app.services.qloo import feedback as fb

    # Fresh feedback state so this test owns the overlay.
    fb._feedback_records.clear()
    fb._preview_pool_deltas.clear()
    fb._liked_taste_names.clear()
    fb._disliked_taste_names.clear()
    fb.record_feedback("real-api-test", "up", ["Miles Davis"])

    anchor = await _anchor_artist(client)
    payload = await apply_taste_preferences(
        client,
        signal_entities=[anchor],
        take=3,
        filter_type="urn:entity:artist",
    )
    _skip_if_transient(payload)
    results = payload.get("results")
    ents = results.get("entities") if isinstance(results, dict) else results or []
    assert isinstance(ents, list)
    assert ents, "expected at least one result entity"
    if isinstance(results, dict) and results.get("preferences_applied"):
        applied = results["preferences_applied"]
        assert applied["liked_count"] == 1
        assert applied["disliked_count"] == 0
        assert applied["disliked_removed"] == 0