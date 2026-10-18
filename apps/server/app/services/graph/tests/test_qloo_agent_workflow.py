"""B档：Qloo Agent 完整编排图（意图分支 + 重试回环 + 格式化/回退）回归测试。

验证点：
1. `classify_intent` / `route_intent`：规则关键词意图分类与分支路由（无本地 LLM）。
2. `check_qloo_result`：成功 / 瞬时错误 / 空结果 / 重试耗尽 / Qloo 禁用 的决策表。
3. `build_qloo_agent_graph()` 可编译，且无 checkpointer（红线：不开启会话持久化）。
4. `graph.ainvoke()` 端到端：
   - qloo 意图 + 成功解析 → `format_output`（taste_data_source=live，qloo_raw_response 记录）；
   - 未知意图 → `fallback_node`（无 live 数据，fallback_message 说明原因）；
   - Qloo 瞬时失败 → 重试回环，重试后成功（retry_count=1, retry_triggered=True）；
   - 重试耗尽 → `fallback_node`（retry_count=2）；
   - 空结果（search 无命中）→ 最多重试 2 次 → `fallback_node`；
   - client disabled（无 key）→ `fallback_node` 降级 preview，不 hard-fail。
5. 节点单元行为：`input_node` / `build_qloo_query` / `retry_node` / `format_output` /
   `fallback_node`。
6. `draw_mermaid()` 返回完整拓扑文本（README / Devpost 展示用）。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.services.graph.checkers import (
    MAX_QLOO_RETRIES,
    QLOO_INTENT,
    UNKNOWN_INTENT,
    check_qloo_result,
    classify_intent,
    route_intent,
)
from app.services.graph.graph import build_qloo_agent_graph, draw_mermaid
from app.services.graph.nodes import (
    build_qloo_query,
    fallback_node,
    format_output,
    input_node,
    retry_node,
)

pytestmark = pytest.mark.anyio


def _make_enabled_mock_client() -> AsyncMock:
    client = AsyncMock()
    client.enabled = True
    client.insights = AsyncMock(return_value={"results": {"entities": []}})
    client.search = AsyncMock(return_value={"results": {"entities": []}})
    return client


async def _no_recs(*args, **kwargs):
    return {"recommendations": [], "results_entities": [], "type": "plain"}


async def _no_cross(*args, **kwargs):
    return {}


async def _no_context(*args, **kwargs):
    return ""


async def _fake_search(*args, **kwargs):
    return [{"entity_id": "e-sinatra", "name": "Frank Sinatra", "type": "urn:entity:artist", "domain": "music"}]


# ===== 1. 意图分类与分支路由 =====

class TestClassifyIntent:
    def test_english_dining_signal(self):
        assert classify_intent("Recommend a dinner for Maria") == QLOO_INTENT
        assert classify_intent("What would he enjoy eating tonight?") == QLOO_INTENT

    def test_demo_message(self):
        msg = "My grandpa loves Frank Sinatra and Italian food but needs low-sodium meals. What would he enjoy?"
        assert classify_intent(msg) == QLOO_INTENT

    def test_chinese_dining_signal(self):
        assert classify_intent("请推荐适合老年人的低盐晚餐") == QLOO_INTENT

    def test_unknown_intent(self):
        assert classify_intent("What's the weather today?") == UNKNOWN_INTENT
        assert classify_intent("") == UNKNOWN_INTENT


class TestRouteIntent:
    def test_qloo_intent_routes_to_build_qloo_query(self):
        assert route_intent({"intent": QLOO_INTENT}) == "build_qloo_query"

    def test_unknown_intent_routes_to_fallback(self):
        assert route_intent({"intent": UNKNOWN_INTENT}) == "fallback_node"

    def test_defensive_reclassify_when_intent_missing(self):
        # intent 缺失（状态合并异常）时按 raw_query 重新分类。
        assert route_intent({"raw_query": "Recommend a dinner"}) == "build_qloo_query"
        assert route_intent({"raw_query": "Hello there"}) == "fallback_node"


# ===== 2. 重试回环决策表 =====

class TestCheckQlooResult:
    def test_success_routes_to_format_output(self):
        assert check_qloo_result({"qloo_enabled": True, "qloo_resolved_names": ["Frank Sinatra"]}) == "format_output"

    def test_error_routes_to_retry(self):
        assert check_qloo_result({"retry_count": 0, "last_error": "boom", "qloo_enabled": False}) == "retry_node"

    def test_error_exhausted_routes_to_fallback(self):
        assert check_qloo_result({"retry_count": MAX_QLOO_RETRIES, "last_error": "boom"}) == "fallback_node"

    def test_disabled_routes_to_fallback_without_retry(self):
        assert check_qloo_result({"qloo_enabled": False, "retry_count": 0}) == "fallback_node"

    def test_empty_result_routes_to_retry(self):
        assert check_qloo_result({"qloo_enabled": True, "qloo_resolved_names": [], "qloo_recommendations": [], "retry_count": 0}) == "retry_node"

    def test_empty_result_exhausted_routes_to_fallback(self):
        assert check_qloo_result({"qloo_enabled": True, "qloo_resolved_names": [], "qloo_recommendations": [], "retry_count": MAX_QLOO_RETRIES}) == "fallback_node"


# ===== 3. 图可编译 + 无 checkpointer（红线） + Mermaid 拓扑 =====

def test_qloo_agent_graph_compiles_without_checkpointer() -> None:
    graph = build_qloo_agent_graph()
    assert getattr(graph, "checkpointer", None) is None


def test_draw_mermaid_returns_full_topology() -> None:
    text = draw_mermaid()
    assert "START --> input_node" in text
    assert "intent_node -->|route_intent: qloo_recommend| build_qloo_query" in text
    assert "retry_node --> qloo_call_node" in text
    assert "format_output --> END" in text
    assert "fallback_node --> END" in text


# ===== 4. 节点单元行为 =====

class TestInputNode:
    def test_normalizes_entities_and_retry_count(self):
        out = input_node(
            {
                "raw_query": "  Recommend a dinner  ",
                "entities": {"cultural_likes": "Jazz", "target_domain": None},
                "retry_count": "3",
            }
        )
        assert out["raw_query"] == "  Recommend a dinner  "
        assert out["entities"] == {"cultural_likes": ["Jazz"], "target_domain": ""}
        assert out["retry_count"] == 3
        assert out["last_error"] is None


class TestBuildQlooQuery:
    def test_merges_entities_and_message_likes(self):
        out = build_qloo_query(
            {"raw_query": "grandpa loves Frank Sinatra", "entities": {"cultural_likes": ["Italian food"], "target_domain": "dining"}}
        )
        assert out["qloo_seed_names"] == ["Italian food", "Frank Sinatra"]
        assert out["qloo_target_domain"] == "dining"
        assert out["qloo_query"]["seed_names"] == ["Italian food", "Frank Sinatra"]

    def test_falls_back_to_raw_query_when_no_seeds(self):
        out = build_qloo_query({"raw_query": "dinner", "entities": {"cultural_likes": [], "target_domain": ""}})
        assert out["qloo_seed_names"] == ["dinner"]


class TestRetryNode:
    def test_increments_and_clears_error(self):
        out = retry_node({"retry_count": 1, "last_error": "timeout", "qloo_resolved_names": [], "qloo_recommendations": []})
        assert out["retry_count"] == 2
        assert out["last_error"] is None
        assert out["retry_triggered"] is True
        assert "timeout" in out["qloo_retry_reason"]


class TestFormatOutput:
    def test_marks_live_when_enabled(self):
        assert format_output({"qloo_enabled": True, "taste_data_source": ""}) == {"taste_data_source": "live"}

    def test_preview_when_disabled(self):
        assert format_output({"qloo_enabled": False}) == {"taste_data_source": "preview"}


class TestFallbackNode:
    def test_reason_for_disabled(self):
        out = fallback_node({"qloo_enabled": False})
        assert out["qloo_enabled"] is False
        assert out["taste_data_source"] == "preview"
        assert "no key" in out["fallback_message"]

    def test_reason_for_unknown_intent(self):
        out = fallback_node({"qloo_enabled": True, "intent": "unknown"})
        assert "intent" in out["fallback_message"]

    def test_reason_for_exhausted_error(self):
        out = fallback_node({"qloo_enabled": False, "last_error": "boom"})
        assert "degraded" in out["fallback_message"]
        assert out["last_error"] is None



# ===== 5. 端到端 ainvoke =====

async def test_ainvoke_happy_path_resolves_and_formats() -> None:
    """qloo 意图 + 成功解析 → format_output：live 标记 + qloo_raw_response 记录。"""
    client = _make_enabled_mock_client()
    graph = build_qloo_agent_graph()
    with patch("app.services.qloo.client.get_qloo_client", return_value=client), \
         patch("app.services.qloo.taste.search_cultural_entities", new=_fake_search), \
         patch("app.services.qloo.taste.get_taste_based_recommendations", new=_no_recs), \
         patch("app.services.qloo.taste.get_cross_domain_discovery", new=_no_cross), \
         patch("app.services.qloo.taste.build_cultural_context_for_llm", new=_no_context):
        result = await graph.ainvoke(
            {"raw_query": "My grandpa loves Frank Sinatra.", "entities": {"cultural_likes": ["Frank Sinatra"], "target_domain": "music"}}
        )

    assert result.get("qloo_enabled") is True
    assert result.get("qloo_resolved_names") == ["Frank Sinatra"]
    assert result.get("taste_data_source") == "live"
    assert result.get("intent") == QLOO_INTENT
    assert result.get("retry_count", 0) == 0
    assert result.get("qloo_raw_response", {}).get("resolved_names") == ["Frank Sinatra"]
    assert result.get("fallback_message") in (None, "")


async def test_ainvoke_unknown_intent_falls_back() -> None:
    """未知意图 → fallback_node：无 live 数据，且从不触碰 Qloo 调用。"""
    client = _make_enabled_mock_client()
    graph = build_qloo_agent_graph()
    with patch("app.services.qloo.client.get_qloo_client", return_value=client):
        result = await graph.ainvoke({"raw_query": "What's the weather today?"})

    assert result.get("intent") == UNKNOWN_INTENT
    assert result.get("qloo_enabled") is False
    assert result.get("taste_data_source") == "preview"
    assert "intent" in result.get("fallback_message", "")
    assert not result.get("qloo_resolved_names")


async def test_ainvoke_transient_error_then_success_retries_once() -> None:
    """Qloo 瞬时失败 → retry_node 回环 → 重试成功：retry_count=1 + live 标记。"""
    client = _make_enabled_mock_client()
    calls = {"n": 0}

    def flaky_client():
        calls["n"] += 1
        if calls["n"] == 1:
            raise ConnectionError("simulated transient qloo failure")
        return client

    graph = build_qloo_agent_graph()
    with patch("app.services.qloo.client.get_qloo_client", side_effect=flaky_client), \
         patch("app.services.qloo.taste.search_cultural_entities", new=_fake_search), \
         patch("app.services.qloo.taste.get_taste_based_recommendations", new=_no_recs), \
         patch("app.services.qloo.taste.get_cross_domain_discovery", new=_no_cross), \
         patch("app.services.qloo.taste.build_cultural_context_for_llm", new=_no_context):
        result = await graph.ainvoke(
            {"raw_query": "My grandpa loves Frank Sinatra.", "entities": {"cultural_likes": ["Frank Sinatra"], "target_domain": "music"}}
        )

    assert calls["n"] == 2
    assert result.get("retry_count") == 1
    assert result.get("retry_triggered") is True
    assert result.get("qloo_enabled") is True
    assert result.get("qloo_resolved_names") == ["Frank Sinatra"]
    assert result.get("taste_data_source") == "live"
    assert result.get("last_error") in (None, "")

async def test_ainvoke_retry_exhausted_falls_back() -> None:
    """Qloo 持续失败 → 最多重试 2 次 → fallback_node（retry_count=2，诚实降级）。"""
    def always_boom():
        raise ConnectionError("simulated persistent qloo failure")

    graph = build_qloo_agent_graph()
    with patch("app.services.qloo.client.get_qloo_client", side_effect=always_boom):
        result = await graph.ainvoke(
            {"raw_query": "My grandpa loves Frank Sinatra.", "entities": {"cultural_likes": ["Frank Sinatra"], "target_domain": "music"}}
        )

    assert result.get("retry_count") == MAX_QLOO_RETRIES
    assert result.get("retry_triggered") is True
    assert result.get("qloo_enabled") is False
    assert result.get("taste_data_source") == "preview"
    assert "degraded" in result.get("fallback_message", "")
    assert not result.get("qloo_resolved_names")


async def test_ainvoke_empty_search_retries_then_falls_back() -> None:
    """搜索无命中（空结果）→ 最多重试 2 次 → fallback_node。"""
    client = _make_enabled_mock_client()

    async def no_hits(*args, **kwargs):
        return []

    graph = build_qloo_agent_graph()
    with patch("app.services.qloo.client.get_qloo_client", return_value=client), \
         patch("app.services.qloo.taste.search_cultural_entities", new=no_hits), \
         patch("app.services.qloo.taste.get_taste_based_recommendations", new=_no_recs), \
         patch("app.services.qloo.taste.get_cross_domain_discovery", new=_no_cross), \
         patch("app.services.qloo.taste.build_cultural_context_for_llm", new=_no_context):
        result = await graph.ainvoke(
            {"raw_query": "Recommend a dinner for Maria", "entities": {"cultural_likes": ["nobody knows this"], "target_domain": "dining"}}
        )

    assert result.get("retry_count") == MAX_QLOO_RETRIES
    assert result.get("retry_triggered") is True
    assert result.get("qloo_enabled") is False
    assert result.get("taste_data_source") == "preview"
    assert "no resolvable cultural anchors" in result.get("fallback_message", "")


async def test_ainvoke_qloo_disabled_no_hard_fail() -> None:
    """client disabled（无 key）→ fallback 降级 preview，不抛错、不重试。"""
    client = AsyncMock()
    client.enabled = False

    graph = build_qloo_agent_graph()
    with patch("app.services.qloo.client.get_qloo_client", return_value=client):
        result = await graph.ainvoke(
            {"raw_query": "My grandpa loves Frank Sinatra.", "entities": {"cultural_likes": ["Frank Sinatra"], "target_domain": "music"}}
        )

    assert result.get("qloo_enabled") is False
    assert result.get("retry_count", 0) == 0
    assert result.get("retry_triggered") in (None, False)
    assert result.get("taste_data_source") == "preview"
    assert "no key" in result.get("fallback_message", "")
    assert result.get("last_error") in (None, "")
