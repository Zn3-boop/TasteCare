"""A档保底：最简 LangGraph StateGraph（qloo_cultural_recommend_node 入图）回归测试。

验证点：
1. `build_agent_graph(minimal=True)` 可编译，无 checkpointer（红线：不开启会话持久化）。
2. `route_main_flow` 固定路由到 qloo_cultural_recommend_node（其余路由函数为占位存根）。
3. `graph.ainvoke()` 真实执行 qloo_cultural_recommend_node，qloo_resolved_names /
   taste_entities 经 StateGraph 状态 merge 保留。
4. client disabled（无 QLOO_API_KEY）时不 hard-fail，qloo_enabled=False 且 taste 为空。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.graph.graph import build_agent_graph
from app.services.graph.checkers import (
    route_main_flow,
    route_after_qloo,
    route_after_llm,
    route_fallback,
)

pytestmark = pytest.mark.anyio


def _make_enabled_mock_client() -> AsyncMock:
    client = AsyncMock()
    client.enabled = True
    # /v2/insights payload shape used by _extract_entities()
    client.insights = AsyncMock(
        return_value={"results": {"entities": []}}
    )
    client.search = AsyncMock(return_value={"results": {"entities": []}})
    return client


def test_route_main_flow_fixed_route() -> None:
    """A档：route_main_flow 固定返回 qloo_cultural_recommend_node，忽略输入内容。"""
    assert route_main_flow({"raw_query": "anything", "entities": {}}) == "qloo_cultural_recommend_node"
    assert route_main_flow({"raw_query": ""}) == "qloo_cultural_recommend_node"


def test_other_routers_are_stubs() -> None:
    """历史存根（A档遗留）：行为不变，B档路由已由 route_intent / check_qloo_result 承担。"""
    assert route_after_qloo({}) in ("qloo_cultural_recommend_node", "__end__")
    assert route_after_llm({}) in ("qloo_cultural_recommend_node", "__end__")
    assert route_fallback({}) == "__end__"


def test_minimal_graph_compiles_without_checkpointer() -> None:
    """最简图可编译，且不携带 checkpointer（红线：不开启会话持久化）。"""
    graph = build_agent_graph(minimal=True)
    # CompiledStateGraph 无 checkpointer 时 checkpoint 为 None
    assert getattr(graph, "checkpointer", None) is None


async def test_minimal_graph_ainvoke_resolves_and_merges_qloo_state() -> None:
    """graph.ainvoke 真实执行 qloo_cultural_recommend_node，state 保留 qloo 字段。"""
    client = _make_enabled_mock_client()

    async def fake_search(*args, **kwargs):
        return [{"entity_id": "e-sinatra", "name": "Frank Sinatra", "type": "urn:entity:artist", "domain": "music"}]

    graph = build_agent_graph(minimal=True)
    with patch("app.services.qloo.client.get_qloo_client", return_value=client), \
         patch("app.services.qloo.taste.search_cultural_entities", new=fake_search):
        result = await graph.ainvoke(
            {
                "raw_query": "grandpa loves Frank Sinatra",
                "entities": {"cultural_likes": ["Frank Sinatra"], "target_domain": "music"},
            }
        )

    assert result.get("qloo_enabled") is True
    assert result.get("qloo_resolved_names") == ["Frank Sinatra"]
    assert result.get("qloo_seed_names") == ["Frank Sinatra"]
    assert isinstance(result.get("taste_entities"), list)


async def test_minimal_graph_ainvoke_qloo_disabled_no_hard_fail() -> None:
    """client disabled（无 QLOO_API_KEY）：图执行成功但 qloo_enabled=False，不抛错。"""
    client = AsyncMock()
    client.enabled = False

    graph = build_agent_graph(minimal=True)
    with patch("app.services.qloo.client.get_qloo_client", return_value=client):
        result = await graph.ainvoke(
            {"raw_query": "Recommend a dinner", "entities": {"cultural_likes": ["Jazz"]}}
        )

    assert result.get("qloo_enabled") is False
    assert result.get("qloo_resolved_names", []) == []
    assert result.get("last_error") in (None, "")
