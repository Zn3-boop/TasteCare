"""Qloo grounding integration tests.

Since chat.py has been simplified to direct LLM calls (no orchestrator/executor),
these tests verify the feedback endpoint and Qloo client grounding still work correctly.
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


class _FakeProvider:
    """Minimal stand-in for app.services.llm.provider.provider (duck-typed)."""

    def __init__(self, captured, chat_fn, *, enabled=True):
        self.captured = captured
        self._chat = chat_fn
        self.enabled = enabled

    async def chat(self, *, system_prompt: str, user_prompt: str, **kw) -> str:
        self.captured["system"] = system_prompt
        self.captured["user"] = user_prompt
        return await self._chat(system_prompt=system_prompt, user_prompt=user_prompt, **kw)


def _mock_qloo_client_enabled_false():
    mock_client = AsyncMock()
    mock_client.enabled = False
    return mock_client


def test_chat_feedback_grounds_in_qloo_taste_context():
    feedback_store.reset_feedback_stores()
    with patch(
        "app.services.qloo.client.get_qloo_client",
        return_value=_mock_qloo_client_enabled_false(),
    ):
        resp = client.post(
            "/api/v1/chat/feedback",
            json={
                "message_id": "msg-grounding-1",
                "thumb": "up",
                "taste_entities": ["Jiangnan light braised cuisine", "Soft steamed vegetables"],
            },
        )

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["ok"] is True
    assert payload["data_source"] == "preview"
    assert payload["recorded"] is True


def test_chat_feedback_plain_reply_keeps_grounding_defaults():
    feedback_store.reset_feedback_stores()
    with patch(
        "app.services.qloo.client.get_qloo_client",
        return_value=_mock_qloo_client_enabled_false(),
    ):
        resp = client.post(
            "/api/v1/chat/feedback",
            json={
                "message_id": "msg-plain-1",
                "thumb": "down",
                "taste_entities": [],
            },
        )

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["ok"] is True
    assert payload["thumb"] == "down"


# ===== /chat/agent must never hard-fail when the LLM synthesis call dies =====
# Regression for the P0 demo bug: an LLM outage (rate limit / timeout / revoked
# key) used to surface as an unhandled exception -> HTTP 500. The endpoint must
# degrade to the deterministic Qloo-only composer (keeping real grounding) or to
# a preview-mode message — never a server error.

def _patch_llm_provider_fails(chat_side_effect):
    """Patch the shared provider so provider.enabled=True but provider.chat raises."""
    return patch(
        "app.services.llm.provider.provider",
        spec=("enabled", "chat", "timeout"),
        **{
            "enabled": True,
            "timeout": 45.0,
            "chat": AsyncMock(side_effect=chat_side_effect),
        },
    )


def test_chat_agent_llm_outage_with_qloo_grounding_degrades_to_qloo_only_reply():
    """LLM synthesis fails AFTER the LangGraph run resolved real Qloo anchors:
    the reply must stay culturally grounded (live) and never raise a 500."""

    async def fake_search(client, query, domain=None, limit=1):
        return [{"entity_id": "E1", "name": "Frank Sinatra", "type": "urn:entity:artist", "domain": "music"}]

    async def fake_recs(client, seed_ids, target_domain=None, limit=10, store=None):
        return {"recommendations": [{"name": "Carmine's", "popularity": 0.91}]}

    async def fake_build_context(client, seed_names, target_domain=None, limit=8, store=None):
        return "Qloo context for Frank Sinatra"

    mock_client = AsyncMock()
    mock_client.enabled = True
    with patch("app.services.qloo.client.get_qloo_client", return_value=mock_client), \
         patch("app.services.qloo.taste.search_cultural_entities", side_effect=fake_search), \
         patch("app.services.qloo.taste.get_taste_based_recommendations", side_effect=fake_recs), \
         patch("app.services.qloo.taste.build_cultural_context_for_llm", side_effect=fake_build_context), \
         _patch_llm_provider_fails(lambda **kw: (_ for _ in ()).throw(RuntimeError("LLM outage"))):
        resp = client.post(
            "/api/v1/chat/agent",
            json={"message": "I love Frank Sinatra. Recommend an Italian dinner."},
        )

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["taste_data_source"] == "live"
    assert "Frank Sinatra" in payload["reply"]
    assert payload["taste_entities"]  # grounding evidence still delivered


def test_chat_agent_llm_outage_without_grounding_returns_preview_message():
    """LLM synthesis fails and no Qloo anchor resolved: a friendly preview-mode
    message must be returned instead of a 500."""

    with patch("app.services.qloo.client.get_qloo_client", return_value=_mock_qloo_client_enabled_false()), \
         _patch_llm_provider_fails(lambda **kw: (_ for _ in ()).throw(RuntimeError("LLM outage"))):
        resp = client.post("/api/v1/chat/agent", json={"message": "What is the weather today?"})

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["taste_data_source"] == "preview"
    # The old raw "LLM connection failed or timed out, no Qloo grounding" is gone:
    # the no-LLM + no-anchor path must return a review-friendly guidance message
    # (user decision: option 2 text as the LAST fallback) — never a bare 500 or a
    # raw technical error surfaced to the demo.
    assert "couldn't resolve a cultural anchor" in payload["reply"]
    assert "Federico Fellini" in payload["reply"]


# ===== /chat/agent must work even without an LLM key (preview fallback) =====

def test_chat_agent_preview_fallback_without_llm_key():
    """Without LLM_API_KEY the endpoint should NOT crash (AsyncOpenAI().chat()
    is a namespace object, not callable) — it returns a preview-mode reply."""
    with patch(
        "app.services.llm.provider.provider",
        spec=("enabled", "chat"),
    ) as mock_provider:
        mock_provider.enabled = False
        resp = client.post("/api/v1/chat/agent", json={"message": "Recommend a dinner for Maria"})

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert "preview" in payload["reply"].lower()
    assert payload["taste_data_source"] == "preview"


def test_chat_agent_qloo_only_composer_live_reply_without_llm():
    """Qloo-only mode: with QLOO_API_KEY set but NO LLM key, /chat/agent must
    still answer — resolved entities + real taste recommendations surfaced from
    the Qloo graph via the composer, labelled live (never preview)."""

    async def fake_search(client, query, limit=1):
        if "sinatra" in query.lower():
            return [{"entity_id": "E1", "name": "Frank Sinatra", "type": "urn:entity:artist", "domain": "music"}]
        return [{"entity_id": "E2", "name": "Italian cuisine", "type": "urn:entity:place", "domain": "dining"}]

    async def fake_recs(client, seed_ids, target_domain=None, limit=10, store=None):
        return {"recommendations": [{"name": "Carmine's", "popularity": 0.91}, {"name": "Il Postino", "popularity": 0.87}]}

    mock_client = AsyncMock()
    mock_client.enabled = True

    mock_provider = AsyncMock()
    mock_provider.enabled = False

    with patch("app.services.llm.provider.provider", mock_provider), \
         patch("app.services.qloo.client.get_qloo_client", return_value=mock_client), \
         patch("app.services.qloo.taste.search_cultural_entities", side_effect=fake_search), \
         patch("app.services.qloo.taste.get_taste_based_recommendations", side_effect=fake_recs):
        resp = client.post(
            "/api/v1/chat/agent",
            json={"message": "My grandpa loves Frank Sinatra and Italian food but needs low-sodium meals."},
        )

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert "Frank Sinatra" in payload["reply"]
    assert "Carmine's" in payload["reply"]
    assert payload["taste_data_source"] == "live"
    assert payload["taste_entities"] and "Frank Sinatra" in payload["taste_entities"]
    assert payload["qloo_context"] and "Qloo Cultural Intelligence" in payload["qloo_context"]


def test_chat_agent_disable_qloo_without_llm_returns_rule_baseline():
    """Ablation integrity fix: with NO LLM key but Qloo enabled, disable_qloo=true
    must return a pure rule-based baseline (taste_data_source='no_qloo') — NOT the
    live Qloo-only composer. Previously the flag was ignored in this path, so both
    ablation columns returned the SAME live Qloo data and the comparison was fake.
    The baseline reply must not leak any Qloo entity names.
    """
    async def fake_search(client, query, limit=1):
        # Would only be reached if the bug regressed (baseline path never searches).
        if "sinatra" in query.lower():
            return [{"entity_id": "E1", "name": "Frank Sinatra", "type": "urn:entity:artist", "domain": "music"}]
        return [{"entity_id": "E2", "name": "Italian cuisine", "type": "urn:entity:place", "domain": "dining"}]

    async def fake_recs(client, seed_ids, target_domain=None, limit=10, store=None):
        return {"recommendations": [{"name": "Carmine's", "popularity": 0.91}]}

    mock_provider = AsyncMock()
    mock_provider.enabled = False
    mock_client = AsyncMock()
    mock_client.enabled = True

    with patch("app.services.llm.provider.provider", mock_provider), \
         patch("app.services.qloo.client.get_qloo_client", return_value=mock_client), \
         patch("app.services.qloo.taste.search_cultural_entities", side_effect=fake_search), \
         patch("app.services.qloo.taste.get_taste_based_recommendations", side_effect=fake_recs):
        resp = client.post(
            "/api/v1/chat/agent",
            json={"message": "My grandpa loves Frank Sinatra and Italian food but needs low-sodium meals.", "disable_qloo": True},
        )

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["taste_data_source"] == "no_qloo"
    assert payload["taste_entities"] == []
    assert "Frank Sinatra" not in payload["reply"]
    assert "Carmine's" not in payload["reply"]
    # The baseline is honest about being generic, not Qloo-grounded.
    assert "no cultural grounding" in payload["reply"].lower()


def test_chat_agent_disable_qloo_is_single_variable_without_llm():
    """Same no-LLM environment, disable_qloo is the ONLY variable: with the flag
    the reply is the rule baseline; without the flag the SAME message resolves
    live Qloo data. This locks the ablation contrast so the web two-column
    comparison is real even when only QLOO_API_KEY is configured."""
    async def fake_search(client, query, limit=1):
        if "sinatra" in query.lower():
            return [{"entity_id": "E1", "name": "Frank Sinatra", "type": "urn:entity:artist", "domain": "music"}]
        return [{"entity_id": "E2", "name": "Italian cuisine", "type": "urn:entity:place", "domain": "dining"}]

    async def fake_recs(client, seed_ids, target_domain=None, limit=10, store=None):
        return {"recommendations": [{"name": "Carmine's", "popularity": 0.91}]}

    mock_provider = AsyncMock()
    mock_provider.enabled = False
    mock_client = AsyncMock()
    mock_client.enabled = True

    payload = {"message": "My grandpa loves Frank Sinatra and Italian food but needs low-sodium meals."}
    with patch("app.services.llm.provider.provider", mock_provider), \
         patch("app.services.qloo.client.get_qloo_client", return_value=mock_client), \
         patch("app.services.qloo.taste.search_cultural_entities", side_effect=fake_search), \
         patch("app.services.qloo.taste.get_taste_based_recommendations", side_effect=fake_recs):
        resp_off = client.post("/api/v1/chat/agent", json={**payload, "disable_qloo": True})
        resp_on = client.post("/api/v1/chat/agent", json=payload)

    off = resp_off.json()
    on = resp_on.json()
    assert resp_off.status_code == 200 and resp_on.status_code == 200
    # The two columns are genuinely different sources.
    assert off["taste_data_source"] == "no_qloo"
    assert on["taste_data_source"] == "live"
    assert off["reply"] != on["reply"]
    assert "Frank Sinatra" in on["reply"] and "Frank Sinatra" not in off["reply"]


def test_chat_agent_qloo_only_composer_falls_back_when_qloo_disabled():
    """Qloo-only mode with Qloo itself disabled -> preview reply (honest), no crash."""
    mock_provider = AsyncMock()
    mock_provider.enabled = False
    mock_client = AsyncMock()
    mock_client.enabled = False

    with patch("app.services.llm.provider.provider", mock_provider), \
         patch("app.services.qloo.client.get_qloo_client", return_value=mock_client):
        resp = client.post("/api/v1/chat/agent", json={"message": "What's good to eat?"})

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert "preview" in payload["reply"].lower()
    assert payload["taste_data_source"] == "preview"


def test_chat_agent_live_grounding_resolves_and_injects_taste_entities():
    """With Qloo enabled, /chat/agent extracts cultural likes from the message,
    resolves them via search_cultural_entities, injects CULTURAL_CONTEXT_INJECTION,
    and returns taste_entities / taste_data_source / qloo_context so the web
    Agent tab can render the QlooGroundingPanel with real evidence."""
    captured = {}

    async def fake_chat(*, system_prompt: str, user_prompt: str, **kw) -> str:
        captured["system"] = system_prompt
        captured["user"] = user_prompt
        return "Top pick: braised short ribs."

    async def fake_search(client, query: str, domain=None, limit=10):
        # Sinatra resolves; everything else falls through (proves no fake hits).
        if "sinatra" in query.lower():
            return [{"entity_id": "E1", "name": "Frank Sinatra", "type": "urn:entity:artist", "domain": "music"}]
        return []

    # Hermetic stubs: the real recipe/context builders route through
    # apply_taste_preferences (AsyncMock client) which emits "coroutine was never
    # awaited" warnings and touches the global feedback pools. Stubbing them keeps
    # this test order-independent and warning-free. qloo_context still renders via
    # chat.py's _format_grounding_context fallback when the node context is empty.
    async def no_recs(*args, **kwargs):
        return {"recommendations": [], "results_entities": [], "type": "plain"}

    async def no_cross(*args, **kwargs):
        return {}

    async def no_context(*args, **kwargs):
        return ""

    fake_provider = _FakeProvider(captured, fake_chat, enabled=True)
    mock_client = AsyncMock()
    mock_client.enabled = True

    with patch("app.services.llm.provider.provider", fake_provider), \
         patch("app.services.qloo.client.get_qloo_client", return_value=mock_client), \
         patch("app.services.qloo.taste.search_cultural_entities", new=fake_search), \
         patch("app.services.qloo.taste.get_taste_based_recommendations", new=no_recs), \
         patch("app.services.qloo.taste.get_cross_domain_discovery", new=no_cross), \
         patch("app.services.qloo.taste.build_cultural_context_for_llm", new=no_context):
        resp = client.post(
            "/api/v1/chat/agent",
            json={"message": "My grandpa loves Frank Sinatra and Italian food but needs low-sodium meals."},
        )

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["reply"] == "Top pick: braised short ribs."
    assert payload["taste_entities"] == ["Frank Sinatra"]
    assert payload["taste_data_source"] == "live"
    assert "Qloo Cultural Intelligence" in (payload["qloo_context"] or "")
    # The prompt actually received the injection block.
    assert "[Qloo Cultural Context]" in captured["user"]
    assert "Frank Sinatra" in captured["user"]
    # The user message is preserved after injection.
    assert "low-sodium meals" in captured["user"]


def test_chat_agent_no_grounding_when_qloo_disabled():
    """Qloo disabled -> NO taste_entities, no injection, empty state — the Agent
    tab must show nothing rather than claiming it grounded in Qloo."""
    captured = {}

    async def fake_chat(*, system_prompt: str, user_prompt: str, **kw) -> str:
        captured["system"] = system_prompt
        captured["user"] = user_prompt
        return "Some reply."

    fake_provider = _FakeProvider(captured, fake_chat, enabled=True)
    mock_client = AsyncMock()
    mock_client.enabled = False

    with patch("app.services.llm.provider.provider", fake_provider), \
         patch("app.services.qloo.client.get_qloo_client", return_value=mock_client):
        resp = client.post(
            "/api/v1/chat/agent",
            json={"message": "My grandpa loves Frank Sinatra."},
        )

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["taste_entities"] == []
    assert payload["taste_data_source"] == ""
    assert payload["qloo_context"] is None
    assert "[Qloo Cultural Context]" not in captured["user"]


def test_chat_agent_uses_cultural_system_prompt():
    """The /chat/agent endpoint wires prompts.py CULTURAL_RECOMMENDATION_SYSTEM_PROMPT
    as the system prompt — proving the templates are in production, not dead code."""
    captured = {}

    async def fake_chat(*, system_prompt: str, user_prompt: str, **kw) -> str:
        captured["system"] = system_prompt
        captured["user"] = user_prompt
        return "Top pick: braised short ribs."

    fake_provider = _FakeProvider(captured, fake_chat, enabled=True)
    with patch("app.services.llm.provider.provider", fake_provider):
        resp = client.post(
            "/api/v1/chat/agent",
            json={"message": "Recommend a dinner for Maria"},
        )

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["reply"] == "Top pick: braised short ribs."
    assert "Qloo" in captured["system"]
    assert "250M+" in captured["system"]
    assert "you don't guess" in captured["system"]
    assert "Maria" in captured["user"]


# ===== /chat/agent live grounding runs THROUGH the compiled LangGraph StateGraph =====

def test_chat_agent_live_grounding_runs_langgraph_stategraph_ainvoke():
    """The live grounding evidence must come from a genuine graph.ainvoke() pass:
    `build_qloo_agent_graph()` compiles the B-tier Qloo agent StateGraph and the
    endpoint awaits `graph.ainvoke(...)`. This asserts the real wiring, not a
    re-implementation of the node's internals.
    """
    captured = {}
    fake_graph = AsyncMock()

    async def fake_ainvoke(state):
        captured["ainvoke_state"] = state
        # Mimic the node's state mutations after execution inside LangGraph.
        merged = dict(state)
        merged.update(
            {
                "qloo_enabled": True,
                "qloo_seed_names": ["Frank Sinatra"],
                "qloo_resolved_names": ["Frank Sinatra"],
                "qloo_taste_context": "[Qloo] Frank Sinatra > jazz + classic pop",
                "taste_entities": [{"entity_id": "E1", "name": "Frank Sinatra"}],
                "last_error": None,
            }
        )
        return merged

    fake_graph.ainvoke = fake_ainvoke

    async def fake_chat(*, system_prompt: str, user_prompt: str, **kw) -> str:
        captured["user"] = user_prompt
        return "Top pick: braised short ribs."

    fake_provider = _FakeProvider(captured, fake_chat, enabled=True)

    with patch("app.services.graph.graph.build_qloo_agent_graph", return_value=fake_graph) as mock_build, \
         patch("app.services.llm.provider.provider", fake_provider):
        resp = client.post(
            "/api/v1/chat/agent",
            json={"message": "My grandpa loves Frank Sinatra."},
        )

    assert mock_build.call_count >= 1
    # chat.py must invoke the B-tier qloo agent graph (intent branching + retry loop).
    assert mock_build.call_args is not None
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["taste_entities"] == ["Frank Sinatra"]
    assert payload["taste_data_source"] == "live"
    assert "Frank Sinatra" in (payload["qloo_context"] or "")
    # The prompt received the graph-produced taste context injection.
    assert "[Qloo Cultural Context]" in captured.get("user", "")
    assert "Frank Sinatra" in captured.get("user", "")


def test_chat_agent_live_grounding_falls_back_when_graph_compile_fails():
    """If StateGraph compilation/execution raises, /chat/agent must degrade back
    to the linear node call — never a hard error, same grounding contract.
    """
    # Test isolation: the feedback registry's session stores persist across
    # requests; prior tests may have written liked/disliked names there. Those
    # leak into profile_likes and, being exact-string deduped, produce duplicate
    # taste_entities. Reset so this test verifies ONLY the graph-compile-failure
    # fallback path.
    from app.services.qloo import feedback as feedback_store
    feedback_store.reset_feedback_stores()

    captured = {}

    async def fake_chat(*, system_prompt: str, user_prompt: str, **kw) -> str:
        captured["user"] = user_prompt
        return "Some reply."

    fake_provider = _FakeProvider(captured, fake_chat, enabled=True)
    mock_client = AsyncMock()
    mock_client.enabled = True

    async def fake_search(*args, **kwargs):
        return [{"entity_id": "E1", "name": "Frank Sinatra", "type": "urn:entity:artist", "domain": "music"}]

    def boom(*args, **kwargs):
        raise RuntimeError("simulated graph compile failure")

    # The real recipe/context builders read the global feedback pools via
    # apply_taste_preferences -> get_liked_taste_names(). Patching them keeps this
    # fallback test hermetic: no cross-test state can influence the assertion.
    async def no_recs(*args, **kwargs):
        return {"recommendations": [], "results_entities": [], "type": "plain"}

    async def no_cross(*args, **kwargs):
        return {}

    async def no_context(*args, **kwargs):
        return ""

    with patch("app.services.graph.graph.build_qloo_agent_graph", side_effect=boom), \
         patch("app.services.llm.provider.provider", fake_provider), \
         patch("app.services.qloo.client.get_qloo_client", return_value=mock_client), \
         patch("app.services.qloo.taste.search_cultural_entities", new=fake_search), \
         patch("app.services.qloo.taste.get_taste_based_recommendations", new=no_recs), \
         patch("app.services.qloo.taste.get_cross_domain_discovery", new=no_cross), \
         patch("app.services.qloo.taste.build_cultural_context_for_llm", new=no_context):
        resp = client.post(
            "/api/v1/chat/agent",
            json={"message": "My grandpa loves Frank Sinatra."},
        )

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    # Linear fallback still grounds on the resolved taste entity.
    assert payload["taste_entities"] == ["Frank Sinatra"]
    assert payload["taste_data_source"] == "live"


# ===== 终版契约①: Qloo 数据实在地注入输出（实体名、分数、位置可追溯） =====
# The grounding context block must expose Qloo's real match score next to every
# entity so "92% → Tony Bennett" style proof is traceable end-to-end, and dining
# venues that cannot be verified in the user's requested city must be REPORTED
# (位置错配就报错), never silently presented as local grounded evidence.

def test_grounding_context_embeds_qloo_match_scores():
    from app.api.chat import _format_grounding_context

    hits = [
        {"name": "Frank Sinatra", "type": "urn:entity:artist", "domain": "music", "score": 0.92},
        {"name": "Tony Bennett", "type": "urn:entity:artist", "domain": "music", "popularity": 0.8},
        {"name": "NoScore", "type": "urn:entity:artist", "domain": "music"},
    ]
    ctx = _format_grounding_context(hits)
    assert "match=92%" in ctx
    assert "match=80%" in ctx
    # No fabricated score for entities Qloo gave no score for.
    assert "match=" not in ctx.split("NoScore")[1][:60]


def test_qloo_only_reply_embeds_match_scores():
    from app.api.chat import _format_qloo_only_reply

    hits = [{"name": "Frank Sinatra", "domain": "music", "score": 0.92}]
    recs = [
        {"name": "Birdland Jazz Club", "popularity": 0.9},
        {"name": "Blue Note NYC", "popularity": 0.75},
    ]
    reply = _format_qloo_only_reply(hits, recs, "My grandpa loves Frank Sinatra in New York")
    assert "92% Qloo match" in reply
    assert "90% Qloo popularity" in reply
    assert "75% Qloo popularity" in reply


def test_entity_matches_location_detects_city_token():
    from app.api.chat import _entity_matches_location

    # Venue name carries an NYC token -> verified True.
    assert _entity_matches_location({"name": "Tony's Steakhouse NYC"}, "New York") is True
    assert _entity_matches_location({"name": "Birdland Jazz Club", "address": "1780 Broadway, New York"}, "New York") is True
    # Venue without any city signal -> False (mismatch reported, not fabricated).
    assert _entity_matches_location({"name": "Mott Street Tavern"}, "New York") is False
    # No requested location -> None (not applicable).
    assert _entity_matches_location({"name": "Mott Street Tavern"}, None) is None
    # Different city token -> False.
    assert _entity_matches_location({"name": "Spiaggia Chicago"}, "New York") is False


def test_verify_dining_location_reports_not_drops():
    from app.api.chat import _verify_dining_location

    recs = [
        {"name": "Le Bernardin NYC", "type": "urn:entity:place"},
        {"name": "Spiaggia Chicago", "type": "urn:entity:place"},
        {"name": "The Modern", "type": "urn:entity:place", "address": "9 W 53rd St, New York"},
    ]
    verified, mismatched = _verify_dining_location(recs, "New York")
    # Verified NYC venues stay; the wrong-city / unverifiable venue is REPORTED
    # in the mismatch list (never silently dropped and never relabelled).
    assert [v["name"] for v in verified] == ["Le Bernardin NYC", "The Modern"]
    assert [m["name"] for m in mismatched] == ["Spiaggia Chicago"]
    # Without a requested location everything stays verified.
    verified_all, mism_all = _verify_dining_location(recs, None)
    assert len(verified_all) == len(recs) and mism_all == []
# ===== 7 域目标识别契约 =====
# The Tastes tab has 7 domain pills (All / Music / Film / Dining / Fashion /
# Travel / Podcast / Books). _domains_for_message must recognize a goal phrase
# for EVERY one of those domains (not just the original 4), and the
# "preference vs request" fix must keep explicit goals ranked above passive
# preference vocabulary.

def test_domains_for_message_covers_all_seven_goal_domains():
    from app.api.chat import _domains_for_message

    cases = {
        "music": "I want to listen to music tonight",
        "film": "where should I watch a movie tonight",
        "dining": "where should I go out to eat",
        "fashion": "what should I wear to the party",
        "travel": "where should I go for a trip this summer",
        "podcast": "can you recommend a podcast about food",
        "book": "recommend a book to read on vacation",
    }
    for domain, msg in cases.items():
        assert _domains_for_message(msg)[0] == domain, f"{msg!r} -> {_domains_for_message(msg)}"


def test_domains_for_message_goal_beats_preference_seed():
    from app.api.chat import _domains_for_message

    # Preference vocabulary ("love food", "Midwestern") must NOT override the
    # explicit goal ("watch a movie"): film is primary, dining is a seed domain.
    domains = _domains_for_message("I love Midwestern food but where should I watch a movie?")
    assert domains[0] == "film"
    assert "film" in domains and "dining" in domains


def test_domains_for_message_goal_only_without_preferences():
    from app.api.chat import _domains_for_message

    assert _domains_for_message("what to listen to")[0] == "music"


def test_domains_for_message_combined_goal_multi():
    from app.api.chat import _domains_for_message

    # Combined requests keep BOTH targets (not truncated to the first found).
    domains = _domains_for_message("where to eat then what to wear")
    assert "dining" in domains and "fashion" in domains


def test_domains_for_message_podcast_not_confused_with_music():
    from app.api.chat import _domains_for_message

    # Regression: a bare "listen to" match used to steal podcast requests into
    # music. "listen to a podcast" must route to podcast, not music.
    domains = _domains_for_message("listen to a podcast about jazz")
    assert domains[0] == "podcast", domains


def test_domain_for_message_returns_primary():
    from app.api.chat import _domain_for_message

    assert _domain_for_message("where should I watch a movie") == "film"
    assert _domain_for_message("what should I wear") == "fashion"
    assert _domain_for_message("no cultural ask here") is None


def test_format_no_qloo_rule_baseline_adapts_target_domain():
    from app.api.chat import _format_no_qloo_rule_baseline

    dining = _format_no_qloo_rule_baseline("where should I go out to eat")
    assert "meal options" in dining
    film = _format_no_qloo_rule_baseline("where should I watch a movie")
    assert "drama films" in film
    book = _format_no_qloo_rule_baseline("recommend a book to read")
    assert "bestseller-list" in book
    travel = _format_no_qloo_rule_baseline("where should I go for a trip")
    assert "well-trodden destinations" in travel


def test_format_qloo_only_reply_surfaces_target_domain():
    from app.api.chat import _format_qloo_only_reply

    hits = [{"name": "Frank Sinatra", "domain": "music", "score": 0.92}]
    reply = _format_qloo_only_reply(
        hits, [], "I love jazz but where should I watch a movie", target_domain="film"
    )
    assert "movie/film recommendations" in reply
    assert "Frank Sinatra" in reply


# ===== Phase 4 regression: "which fashionable place can i go to" routing + persona binding =====
# Three user-reported defects:
#   (a) "which fashionable place can i go to" was routed to dining (the dining
#       preference word "food" won because no travel/fashion goal phrase matched);
#   (b) the Qloo-only reply listed the RESOLVED ANCHOR SEEDS under a
#       "recommendations" heading, so seeds looked like recommendations;
#   (c) the "🔗 Bound to Maria" AgentTab badge was cosmetic — /chat/agent never
#       received the persona's taste anchors, so recommendations ignored them.

def test_domains_for_message_fashionable_place_routes_away_from_dining():
    from app.api.chat import _domains_for_message

    # The user's exact reported query. "place can i go" is a travel goal phrase,
    # "fashion" is explicit fashion vocabulary — either way the PRIMARY goal must
    # NOT be dining (dining was only reached because the old phrase table had no
    # travel/fashion goal match and the preference layer fell back to "food").
    domains = _domains_for_message("which fashionable place can i go to")
    assert domains[0] in ("travel", "fashion"), domains
    # travel goal + fashion vocab coexist; dining must never be the primary.
    assert "dining" not in domains[:1]


def test_domains_for_message_travel_phrases_do_not_steal_dining():
    from app.api.chat import _domains_for_message

    # Regression guard: the new "place can i go" phrase family must not hijack
    # "where can i go out to eat" into travel.
    assert _domains_for_message("where can i go out to eat in New York")[0] == "dining"
    assert _domains_for_message("where should i go to eat dinner")[0] == "dining"


def test_persona_anchor_likes_splits_comma_list():
    from app.api.chat import _persona_anchor_likes

    anchors = _persona_anchor_likes("Frank Sinatra, Jazz, Italian cuisine, 中国菜,   Classic Hollywood films")
    assert anchors == ["Frank Sinatra", "Jazz", "Italian cuisine", "中国菜", "Classic Hollywood films"]


def test_persona_anchor_likes_empty_and_dedup():
    from app.api.chat import _persona_anchor_likes

    assert _persona_anchor_likes("") == []
    assert _persona_anchor_likes(None) == []
    assert _persona_anchor_likes("Frank Sinatra, frank sinatra, Jazz") == ["Frank Sinatra", "Jazz"]


def test_format_qloo_only_reply_separates_seeds_from_recommendations():
    from app.api.chat import _format_qloo_only_reply

    hits = [{"name": "Frank Sinatra", "domain": "music", "score": 0.92}]
    recs = [{"name": "Paisley Cafe", "popularity": 0.8}]
    reply = _format_qloo_only_reply(
        hits, recs, "which fashionable place can i go to", target_domain="fashion",
        persona_name="Maria",
    )
    # The persona is named, the seed is listed as a SEED (not a recommendation),
    # and the real Qloo recommendation carries the labelled section.
    assert "You're chatting as Maria" in reply
    assert "Cultural anchor seeds resolved" in reply
    assert "Frank Sinatra" in reply
    assert "Recommendations grounded in those anchors" in reply
    assert "Paisley Cafe" in reply
    # Regression: the old wording listed hits under "Here's what the Qloo taste
    # graph surfaced" — seeds must never be framed as recommendations.
    assert "Here's what the Qloo taste graph surfaced" not in reply


def test_format_qloo_only_reply_empty_recs_is_explicit():
    from app.api.chat import _format_qloo_only_reply

    hits = [{"name": "Frank Sinatra", "domain": "music"}]
    reply = _format_qloo_only_reply(hits, [], "which fashionable place can i go to", target_domain="travel")
    assert "anchor seeds" in reply
    assert "did not return taste-graph recommendations" in reply
    # No fake rec section when Qloo returned none.
    assert "Recommendations grounded in those anchors" not in reply


def test_chat_agent_qloo_only_uses_persona_anchors_when_message_has_none():
    """Qloo-only path must ground on persona anchors even when the message
    itself contains no explicit cultural like ("which fashionable place can i
    go to" has no 'I love X' clause)."""
    from unittest.mock import AsyncMock, patch

    fake_client = AsyncMock()
    fake_client.enabled = True
    captured = {}

    async def fake_search(client, query, limit=None, domain=None):
        captured["query"] = query
        if "library" in query.lower():
            return [{"entity_id": "lib-1", "name": "The New York Public Library", "type": "places"}]
        return []

    async def no_recs(*args, **kwargs):
        return {"recommendations": [], "results_entities": [], "type": "plain"}

    with patch("app.services.qloo.client.get_qloo_client", return_value=fake_client), \
         patch("app.services.llm.provider.provider", spec=("enabled", "chat", "timeout"), **{
             "enabled": False, "timeout": 45.0, "chat": AsyncMock(),
         }), \
         patch("app.services.qloo.taste.search_cultural_entities", new=fake_search), \
         patch("app.services.qloo.taste.get_taste_based_recommendations", new=no_recs):
        resp = client.post(
            "/api/v1/chat/agent",
            json={
                "message": "which fashionable place can i go to",
                "persona_name": "Maria",
                "persona_anchors": "The New York Public Library, Jazz",
            },
        )

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["taste_data_source"] == "live", payload
    # The persona's anchor was actually resolved and seeded.
    assert "The New York Public Library" in [h.get("name") for h in payload.get("taste_entity_details", [])]
    assert "Maria" in payload["reply"]

def test_chat_agent_locked_mode_seeds_only_persona_anchors_via_langgraph():
    """persona_mode='locked' must feed the Qloo node a PURE persona seed list:
    the message's own cultural likes (e.g. 'Christopher Nolan') and the fixed
    core anchors (classic Chicago blues / mid-century modern design / craft
    jazz vinyl records) are BOTH dropped — the seed list is exactly the
    persona's saved anchors, so the agent never invents new entities from the
    question text."""
    captured = {}
    fake_graph = AsyncMock()

    async def fake_ainvoke(state):
        captured["ainvoke_state"] = state
        merged = dict(state)
        merged.update(
            {
                "qloo_enabled": True,
                "qloo_seed_names": state["entities"]["cultural_likes"],
                "qloo_resolved_names": state["entities"]["cultural_likes"],
                "qloo_taste_context": "[Qloo] persona-anchored seeds",
                "taste_entities": [{"entity_id": "E1", "name": "Frank Sinatra"}],
                "last_error": None,
            }
        )
        return merged

    fake_graph.ainvoke = fake_ainvoke

    async def fake_chat(*, system_prompt: str, user_prompt: str, **kw) -> str:
        captured["user"] = user_prompt
        return "Locked to the persona profile."

    fake_provider = _FakeProvider(captured, fake_chat, enabled=True)

    with patch("app.services.graph.graph.build_qloo_agent_graph", return_value=fake_graph) as mock_build, \
         patch("app.services.llm.provider.provider", fake_provider):
        resp = client.post(
            "/api/v1/chat/agent",
            json={
                "message": "I love the films of Christopher Nolan — where should I eat in New York?",
                "persona_name": "Maria",
                "persona_anchors": "Frank Sinatra, Italian cuisine, Jazz",
                "persona_mode": "locked",
            },
        )

    assert resp.status_code == 200, resp.text
    assert mock_build.call_count >= 1
    seeds = captured["ainvoke_state"]["entities"]["cultural_likes"]
    # Pure persona read: every seed is a persona anchor.
    assert seeds == ["Frank Sinatra", "Italian cuisine", "Jazz"], seeds
    # Message-derived entities must never leak in.
    assert "Nolan" not in " ".join(seeds)
    assert "Chicago" not in " ".join(seeds)
    # Fixed core anchors must never leak in either.
    for off_profile in ("mid-century modern design", "craft jazz vinyl records"):
        assert off_profile not in " ".join(seeds).lower(), off_profile



def test_chat_agent_mixed_mode_still_merges_message_likes_into_seeds():
    """persona_mode='mixed' (default) keeps the free-exploration contract:
    message-derived likes ARE merged into the Qloo seed list together with the
    persona anchors — the regression guard for the new locked switch."""
    captured = {}
    fake_graph = AsyncMock()

    async def fake_ainvoke(state):
        captured["ainvoke_state"] = state
        merged = dict(state)
        merged.update(
            {
                "qloo_enabled": True,
                "qloo_seed_names": state["entities"]["cultural_likes"],
                "qloo_resolved_names": state["entities"]["cultural_likes"],
                "qloo_taste_context": "[Qloo] mixed seeds",
                "taste_entities": [{"entity_id": "E1", "name": "Frank Sinatra"}],
                "last_error": None,
            }
        )
        return merged

    fake_graph.ainvoke = fake_ainvoke

    async def fake_chat(*, system_prompt: str, user_prompt: str, **kw) -> str:
        captured["user"] = user_prompt
        return "Free exploration."

    fake_provider = _FakeProvider(captured, fake_chat, enabled=True)

    with patch("app.services.graph.graph.build_qloo_agent_graph", return_value=fake_graph), \
         patch("app.services.llm.provider.provider", fake_provider):
        resp = client.post(
            "/api/v1/chat/agent",
            json={
                "message": "I love the films of Christopher Nolan — where should I eat in New York?",
                "persona_name": "Maria",
                "persona_anchors": "Frank Sinatra, Italian cuisine, Jazz",
            },
        )

    assert resp.status_code == 200, resp.text
    seeds = captured["ainvoke_state"]["entities"]["cultural_likes"]
    assert "Frank Sinatra" in seeds
    # Free exploration still pulls message-derived likes into the seed list.
    assert any("Nolan" in s for s in seeds), seeds
    assert any("chicago blues" in s.lower() for s in seeds), seeds


def test_chat_agent_locked_mode_qloo_only_skips_message_likes():
    """Qloo-only (no LLM key) path must honour persona_mode='locked' too: the
    search queries sent to the Qloo client are only the persona's anchors, never
    cultural entities extracted from the question text."""
    from unittest.mock import AsyncMock, patch

    fake_client = AsyncMock()
    fake_client.enabled = True
    captured_queries = []

    async def fake_search(client, query, limit=None, domain=None):
        captured_queries.append(query)
        return [{"entity_id": "E1", "name": "Frank Sinatra", "domain": "music"}]

    async def no_recs(*args, **kwargs):
        return {"recommendations": [], "results_entities": [], "type": "plain"}

    with patch("app.services.qloo.client.get_qloo_client", return_value=fake_client), \
         patch("app.services.llm.provider.provider", spec=("enabled", "chat", "timeout"), **{
             "enabled": False, "timeout": 45.0, "chat": AsyncMock(),
         }), \
         patch("app.services.qloo.taste.search_cultural_entities", new=fake_search), \
         patch("app.services.qloo.taste.get_taste_based_recommendations", new=no_recs):
        resp = client.post(
            "/api/v1/chat/agent",
            json={
                "message": "I love the films of Christopher Nolan — where should I eat in New York?",
                "persona_name": "Maria",
                "persona_anchors": "Frank Sinatra, Italian cuisine, Jazz",
                "persona_mode": "locked",
            },
        )

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["taste_data_source"] == "live", payload
    # Every Qloo search query is a persona anchor — no message-derived entity.
    assert captured_queries, captured_queries
    joined = " ".join(captured_queries).lower()
    assert "nolan" not in joined, joined
    assert "chicago" not in joined, joined
    assert "frank sinatra" in joined


def test_chat_agent_locked_mode_never_emits_didnt_map_fallback():
    """persona_mode='locked' + Qloo resolves NOTHING must NOT emit the generic
    \"didn't map to anything in Qloo's taste graph\" error. In locked mode the
    seed list is a PURE read of the persona's saved anchors — the user can't fix
    \"Frank Sinatra didn't map\" by rephrasing, so the fallback must own the lock
    and point at the exits (unlock, or the Tastes / Senior Dining tabs) instead
    of blaming the request."""
    captured = {}
    fake_graph = AsyncMock()

    async def fake_ainvoke(state):
        captured["ainvoke_state"] = state
        merged = dict(state)
        merged.update(
            {
                # Qloo configured but the node resolved ZERO anchors.
                "qloo_enabled": True,
                "qloo_seed_names": state["entities"]["cultural_likes"],
                "qloo_resolved_names": [],
                "qloo_taste_context": "",
                "taste_entities": [],
                "last_error": None,
            }
        )
        return merged

    fake_graph.ainvoke = fake_ainvoke

    with patch("app.services.graph.graph.build_qloo_agent_graph", return_value=fake_graph), \
         _patch_llm_provider_fails(lambda **kw: (_ for _ in ()).throw(RuntimeError("LLM outage"))):
        resp = client.post(
            "/api/v1/chat/agent",
            json={
                "message": "I want to buy some books — what should I get?",
                "persona_name": "Maria",
                "persona_anchors": "Frank Sinatra, Italian cuisine, Jazz",
                "persona_mode": "locked",
            },
        )

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    # The locked fallback must NEVER surface the generic "couldn't resolve /
    # didn't map" error — that wording tells the user to rephrase, which locked
    # mode deliberately ignores.
    assert "didn't map to anything in Qloo's taste graph" not in payload["reply"]
    assert "couldn't resolve a cultural anchor" not in payload["reply"]
    # Instead it owns the lock honestly.
    assert "locked" in payload["reply"].lower()
    assert "Frank Sinatra" in payload["reply"]
    assert "profile lock OFF" in payload["reply"]


def test_chat_agent_mixed_mode_keeps_generic_didnt_map_fallback():
    """persona_mode='mixed' (default) + Qloo resolves nothing must KEEP the
    existing generic guidance — locked is the only branch that swaps it out."""
    fake_graph = AsyncMock()

    async def fake_ainvoke(state):
        merged = dict(state)
        merged.update(
            {
                "qloo_enabled": True,
                "qloo_seed_names": state["entities"]["cultural_likes"],
                "qloo_resolved_names": [],
                "qloo_taste_context": "",
                "taste_entities": [],
                "last_error": None,
            }
        )
        return merged

    fake_graph.ainvoke = fake_ainvoke

    with patch("app.services.graph.graph.build_qloo_agent_graph", return_value=fake_graph), \
         _patch_llm_provider_fails(lambda **kw: (_ for _ in ()).throw(RuntimeError("LLM outage"))):
        resp = client.post(
            "/api/v1/chat/agent",
            json={"message": "I want to buy some books — what should I get?"},
        )

    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert "didn't map to anything in Qloo's taste graph" in payload["reply"]
