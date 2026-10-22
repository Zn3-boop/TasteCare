"""Chat ablation single-variable consistency tests.

Guarantees the real /chat/agent disable_qloo=true baseline differs from the
with-Qloo branch ONLY by the Qloo entity-context block:

  * both branches receive the SAME CULTURAL_RECOMMENDATION_SYSTEM_PROMPT
  * both branches receive the SAME accumulated user taste-profile likes
  * same temperature, same task_type, same raw user message
  * the With-Qloo branch gets the "[Qloo Cultural Context] ..." block; the
    Without-Qloo branch never does
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
from app.services.qloo.prompts import CULTURAL_RECOMMENDATION_SYSTEM_PROMPT  # noqa: E402

client = TestClient(app)

QLOO_CONTEXT_MARKER = "[Qloo Cultural Context]"
PROFILE_LIKES_MARKER = "[User Taste Profile]"


def _capture_provider(logs):
    """Provider stub that records every chat() call's system/user prompts."""

    class _FakeProvider:
        enabled = True

        async def chat(self, *, system_prompt: str, user_prompt: str, **kw):
            logs.append(
                {"system": system_prompt, "user": user_prompt, **kw}
            )
            return "OK"

    return _FakeProvider()


def _enabled_qloo_client():
    stub = AsyncMock()
    stub.enabled = True
    return stub


def _seed_likes(*names: str) -> None:
    feedback_store.reset_feedback_stores()
    for n in names:
        feedback_store.get_feedback_store().record_feedback(
            message_id=f"seed-{n}", thumb="up", taste_entities=[n]
        )


async def _fake_search(client, query: str, **kw):
    # search_cultural_entities returns a flat list of entity dicts.
    return [
        {"name": query, "entity_id": f"e-{query}", "types": ["urn:entity:artist"], "domain": "music"}
    ]


async def _no_recs(*args, **kwargs):
    return {"recommendations": [], "results_entities": [], "type": "plain"}


async def _no_cross(*args, **kwargs):
    return {}


async def _no_context(*args, **kwargs):
    return ""


def test_ablation_pair_single_variable_consistency():
    """Only the Qloo grounding block differs; system prompt, likes, t., task_type identical."""
    _seed_likes("Jiangnan light braised cuisine", "Frank Sinatra")
    logs = []

    fake_provider = _capture_provider(logs)
    # _no_recs/_no_cross/_no_context keep the with-Qloo graph branch hermetic:
    # the real recipe/context builders route through apply_taste_preferences
    # (AsyncMock client) which emits "coroutine was never awaited" warnings.
    with patch("app.services.llm.provider.provider", fake_provider), \
         patch(
             "app.services.qloo.client.get_qloo_client",
             return_value=_enabled_qloo_client(),
         ), \
         patch(
             "app.services.qloo.taste.search_cultural_entities",
             side_effect=_fake_search,
         ), \
         patch(
             "app.services.qloo.taste.get_taste_based_recommendations",
             new=_no_recs,
         ), \
         patch(
             "app.services.qloo.taste.get_cross_domain_discovery",
             new=_no_cross,
         ), \
         patch(
             "app.services.qloo.taste.build_cultural_context_for_llm",
             new=_no_context,
         ):
        # Fire both branches in parallel with the SAME session/profile state.
        r_with = client.post(
            "/api/v1/chat/agent",
            json={"message": "Please suggest a low-sodium dinner."},
        )
        r_without = client.post(
            "/api/v1/chat/agent",
            json={"message": "Please suggest a low-sodium dinner.", "disable_qloo": True},
        )

    assert r_with.status_code == 200, r_with.text
    assert r_without.status_code == 200, r_without.text
    assert len(logs) == 2, logs

    qloo_call, baseline_call = logs

    # 1) Identical system prompt across both branches.
    assert baseline_call["system"] == CULTURAL_RECOMMENDATION_SYSTEM_PROMPT
    assert qloo_call["system"] == CULTURAL_RECOMMENDATION_SYSTEM_PROMPT

    # 2) Identical model-selection parameters — no hidden drift.
    for key in ("temperature", "task_type"):
        assert (
            qloo_call[key] == baseline_call[key]
        ), f"{key} drifted: {qloo_call[key]} vs {baseline_call[key]}"

    # 3) Taste-profile likes injected in BOTH branches.
    for like in ("Jiangnan light braised cuisine", "Frank Sinatra"):
        assert like in qloo_call["user"], f"with-Qloo missing profile like: {like}"
        assert like in baseline_call["user"], f"baseline missing profile like: {like}"
    assert PROFILE_LIKES_MARKER in baseline_call["user"]

    # 4) Qloo grounding block ONLY in the With-Qloo branch.
    assert QLOO_CONTEXT_MARKER in qloo_call["user"]
    assert QLOO_CONTEXT_MARKER not in baseline_call["user"]

    # 5) The raw user message survives intact in both branches.
    assert "low-sodium dinner" in qloo_call["user"]
    assert "low-sodium dinner" in baseline_call["user"]


def test_disable_qloo_leaves_profile_and_request_but_strips_qloo():
    """The baseline branch keeps raw request + taste profile, and never fabricates Qloo claims."""
    _seed_likes("Jiangnan light braised cuisine")
    logs = []

    fake_provider = _capture_provider(logs)
    with patch("app.services.llm.provider.provider", fake_provider), \
         patch(
             "app.services.qloo.client.get_qloo_client",
             return_value=_enabled_qloo_client(),
         ):
        resp = client.post(
            "/api/v1/chat/agent",
            json={"message": "What should I eat?", "disable_qloo": True},
        )

    assert resp.status_code == 200, resp.text
    assert resp.json()["taste_data_source"] == "no_qloo"
    assert len(logs) == 1
    call = logs[0]
    assert QLOO_CONTEXT_MARKER not in call["user"]
    assert "Jiangnan light braised cuisine" in call["user"]
    assert "What should I eat?" in call["user"]