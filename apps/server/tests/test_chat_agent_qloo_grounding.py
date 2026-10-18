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