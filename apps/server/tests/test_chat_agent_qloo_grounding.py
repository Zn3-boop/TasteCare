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
    feedback_store._feedback_records.clear()
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
    feedback_store._feedback_records.clear()
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

    fake_provider = _FakeProvider(captured, fake_chat, enabled=True)
    mock_client = AsyncMock()
    mock_client.enabled = True

    with patch("app.services.llm.provider.provider", fake_provider), \
         patch("app.services.qloo.client.get_qloo_client", return_value=mock_client), \
         patch("app.services.qloo.taste.search_cultural_entities", new=fake_search):
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