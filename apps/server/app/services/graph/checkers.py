"""Graph condition-router functions and light-weight checker implementations.

档位B（完整）职责：
- 意图分支：`classify_intent`（规则关键词，不引入本地 LLM）→ `route_intent`
  （qloo 意图 → `build_qloo_query`；其它 / unknown → `fallback_node`）。
- 重试回环：`check_qloo_result`（成功 → `format_output`；瞬时错误 / 空结果且
  retry_count < MAX_QLOO_RETRIES → `retry_node`；重试耗尽 / Qloo 禁用 →
  `fallback_node`）。
- 保留 A档保底 `route_main_flow`（固定单路由）与三个历史存根
  （`route_after_qloo` / `route_after_llm` / `route_fallback`），供完整大图与
  旧测试引用。
- 提供完整大图（`build_agent_graph()` 默认路径）与 `nodes.py` 懒导入所引用的
  一组安全最小实现（fast_brain / guard / risk / post_validate）。

红线（与项目全局约束一致）：
- 各档图 compile() 均不传 checkpointer —— 不开启会话持久化。
- 意图路由仅规则关键词判断（无本地 LLM / Ollama）。
"""

from __future__ import annotations

import os
import re
from typing import Any

from langgraph.graph import END

from app.services.graph.state import AgentState

QLOO_RECOMMEND_NODE = "qloo_cultural_recommend_node"


def route_main_flow(state: AgentState) -> str:
    """A档保底路由：主流程固定路由到 Qloo 文化推荐节点。

    拓扑：START → route_main_flow → qloo_cultural_recommend_node → END。
    B档在此基础上扩展为意图分支（route_intent）+ 重试回环（check_qloo_result），
    本函数保持为总入口分发的单一决策点。
    """
    return QLOO_RECOMMEND_NODE


def route_after_qloo(state: AgentState) -> str:
    """历史存根：已由 B档 `check_qloo_result` 取代。保留供完整大图 / 旧测试引用。"""
    return END


def route_after_llm(state: AgentState) -> str:
    """历史存根：完整大图的 LLM 后置路由由 `graph.route_after_llm` 承担。"""
    return QLOO_RECOMMEND_NODE


def route_fallback(state: AgentState) -> str:
    """历史存根：B档回退由 `fallback_node` 承担。"""
    return END


# ---------------------------------------------------------------------------
# B档：意图分支 + 重试回环条件路由
# ---------------------------------------------------------------------------

MAX_QLOO_RETRIES = int(os.getenv("QLOO_MAX_RETRIES", "2"))

QLOO_INTENT = "qloo_recommend"
UNKNOWN_INTENT = "unknown"

# 规则关键词集合（B档红线：意图识别仅规则匹配，无本地 LLM）。
# 英文关键词使用词边界正则（`\beat\b` 不会误命中 "weather"），
# 中文关键词无词边界概念，退化为子串匹配。
_QLOO_INTENT_EN_WORDS = (
    "recommend", "recommendation", "recommendations",
    "suggest", "suggestion", "suggestions",
    "food", "foods", "dinner", "lunch", "breakfast", "meal", "meals",
    "eat", "eats", "eating", "ate",
    "restaurant", "restaurants", "dining", "cuisine", "dish", "dishes",
    "recipe", "recipes", "cook", "cooking", "cooked",
    "snack", "snacks", "menu", "chef", "culinary", "gourmet",
    "taste", "tastes",
    "enjoy", "enjoys", "enjoyed", "enjoying",
    "love", "loves", "loved",
    "like", "likes", "liked",
    "favorite", "favourite", "favorites", "favourites",
    "hungry",
    "fan of", "what would", "would he", "would she",
)
_QLOO_INTENT_CN_WORDS = (
    "推荐", "晚餐", "午餐", "早餐", "美食", "餐厅", "吃什么", "做饭", "菜谱",
)
_QLOO_INTENT_EN_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in _QLOO_INTENT_EN_WORDS) + r")\b",
    re.IGNORECASE,
)


def classify_intent(raw_query: str) -> str:
    """规则关键词意图分类（B档）：命中任一餐饮/推荐信号 → qloo_recommend，否则 unknown。"""
    low = (raw_query or "").lower()
    if _QLOO_INTENT_EN_RE.search(low):
        return QLOO_INTENT
    if any(kw in low for kw in _QLOO_INTENT_CN_WORDS):
        return QLOO_INTENT
    return UNKNOWN_INTENT


def route_intent(state: AgentState) -> str:
    """B档意图条件路由：qloo_recommend → `build_qloo_query`；其余 → `fallback_node`。

    防御性兜底：若 `intent_node` 的输出在状态合并中缺失（intent 为空），
    按 raw_query 重新 `classify_intent`，保证图在缺省状态下不误入 fallback。
    """
    if state.get("intent") == QLOO_INTENT:
        return "build_qloo_query"
    if classify_intent(str(state.get("raw_query", ""))) == QLOO_INTENT:
        return "build_qloo_query"
    return "fallback_node"


def check_qloo_result(state: AgentState) -> str:
    """B档 Qloo 调用结果条件路由（重试回环）。

    决策顺序：
    1. 有 `last_error` 且 retry_count < MAX_QLOO_RETRIES  → `retry_node`（重试）；
    2. 有 `last_error` 且重试耗尽                        → `fallback_node`；
    3. `qloo_enabled=False`（无 key / 降级）              → `fallback_node`（重试无意义）；
    4. 空结果（无解析实体也无推荐）且可重试               → `retry_node`；
    5. 空结果且重试耗尽                                  → `fallback_node`；
    6. 默认成功                                          → `format_output`。
    """
    retries = state.get("retry_count", 0)
    err = state.get("last_error")
    if err and retries < MAX_QLOO_RETRIES:
        return "retry_node"
    if err:
        return "fallback_node"
    if not state.get("qloo_enabled", True):
        return "fallback_node"
    resolved = state.get("qloo_resolved_names") or []
    recs = state.get("qloo_recommendations") or []
    if not resolved and not recs:
        if retries < MAX_QLOO_RETRIES:
            return "retry_node"
        return "fallback_node"
    return "format_output"


# ---------------------------------------------------------------------------
# 完整大图 / nodes.py 懒导入所需的轻量实现（安全最小版本）
# ---------------------------------------------------------------------------

def fast_brain_node(state: AgentState) -> dict[str, Any]:
    """快脑最小实现：直接放行到慢脑意图识别（不调用任何本地 LLM / Ollama）。"""
    return {
        "fast_brain_decision": "proceed",
        "fast_brain_mode": "full_slow",
        "fast_brain_msg": "checker: fast_brain pass-through",
        "fast_brain_result": "",
        "fast_brain_confidence": 1.0,
        "fast_brain_intent": state.get("intent", ""),
    }


def guard_pre_check_node(state: AgentState) -> dict[str, Any]:
    """前置守卫最小实现：直接放行（last_error 置空，route_after_guard → risk_check）。"""
    return {"last_error": None}


def risk_check_node(state: AgentState) -> dict[str, Any]:
    """风险检查最小实现：默认低风险、无需人工审批。"""
    return {
        "risk_level": "low",
        "risk_reason": "checker: default low risk",
        "approval_required": False,
    }


def post_validate_gate(state: AgentState) -> dict[str, Any]:
    """工具后置校验最小实现：无错误放行（route_after_validate → memory_persist）。"""
    return {"last_error": None}
