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
#
# 词表覆盖 Qloo 的全部七个文化域（dining/film/music/book/fashion/travel/
# podcast）+ 需求表达（"want to get"/"looking for" 等），保证 "I want to get
# some books"（用户要书）这类不带 "recommend" 的文化请求也能进入 Qloo 节点。
_QLOO_INTENT_EN_WORDS = (
    "recommend", "recommendation", "recommendations",
    "suggest", "suggestion", "suggestions",
    "advice", "advices", "advise",
    "tell me", "show me", "give me", "help me",
    "what can", "what should", "what would", "what to", "what about",
    "how about", "where can", "where should",
    # dining
    "food", "foods", "dinner", "lunch", "breakfast", "meal", "meals",
    "eat", "eats", "eating", "ate",
    "restaurant", "restaurants", "dining", "cuisine", "dish", "dishes",
    "recipe", "recipes", "cook", "cooking", "cooked",
    "snack", "snacks", "menu", "chef", "culinary", "gourmet",
    "hungry",
    # film / tv
    "watch a movie", "watch a film", "watch movies", "watch films",
    "see a movie", "see a film", "a movie to watch", "a film to watch",
    "movie", "movies", "film", "films", "cinema", "actor", "actress",
    "tv show", "tv shows", "series", "netflix",
    # music
    "music", "song", "songs", "album", "albums", "band", "bands",
    "artist", "artists", "concert", "gig", "vinyl", "record", "records",
    "listen to", "playlist",
    # book
    "book", "books", "read a book", "read some books", "a book to read",
    "novel", "novels", "reading", "author", "literature",
    # fashion
    "wear", "wearing", "outfit", "outfits", "dress", "fashion", "clothes",
    "clothing", "style", "what to wear", "what should i wear", "suit",
    # travel
    "travel", "trip", "trips", "vacation", "holiday", "destination",
    "visit", "go somewhere", "place to go", "places to go", "travel to",
    # podcast
    "podcast", "podcasts",
    # 需求表达：没有推荐动词但仍然是文化请求
    "want to get", "wants to get", "want to buy", "wants to buy",
    "looking for", "need a", "need some", "need to find",
    "get some", "find me",
    # taste profile signals
    "taste", "tastes",
    "enjoy", "enjoys", "enjoyed", "enjoying",
    "love", "loves", "loved",
    "like", "likes", "liked",
    "favorite", "favourite", "favorites", "favourites",
    "fan of", "what would", "would he", "would she",
)
_QLOO_INTENT_CN_WORDS = (
    "推荐", "晚餐", "午餐", "早餐", "美食", "餐厅", "吃什么", "做饭", "菜谱",
    "书", "看书", "读", "买", "穿", "衣服", "旅行", "旅游", "去哪", "哪里",
    "电影", "剧", "音乐会", "音乐", "播客", "逛街", "品牌", "搭配",
)
_QLOO_INTENT_EN_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in _QLOO_INTENT_EN_WORDS) + r")\b",
    re.IGNORECASE,
)


_PURE_CHITCHAT_EN_RE = re.compile(
    r"^(?:hi|hi there|hello|hello there|hey|hey there|good morning|good afternoon|"
    r"good evening|how are you|how's it going|how is it going|thanks|thank you|"
    r"thank you so much|thanks a lot|bye|goodbye|good night|help|help me)$",
    re.IGNORECASE,
)
_PURE_CHITCHAT_CN = (
    "你好", "您好", "早上好", "下午好", "晚上好", "谢谢", "谢谢你", "再见", "拜拜",
)


def _looks_like_chitchat(raw_query: str) -> bool:
    """True for pure social / meta chatter with zero cultural content.

    These messages would produce an EMPTY message-like pool, so sending them to
    the Qloo node wastes a live call (and can confuse the demo with a coffee
    recommendation for a "hello"). Anything else — even without a recommend
    verb ("I want to get some books", "给妈妈买件衣服") — counts as a request.
    """
    low = (raw_query or "").strip().lower()
    if not low:
        return True
    if _PURE_CHITCHAT_EN_RE.match(low):
        return True
    return any(kw in low for kw in _PURE_CHITCHAT_CN)


def classify_intent(raw_query: str) -> str:
    """规则关键词意图分类（B档）：命中任一文化/推荐信号 → qloo_recommend，否则 unknown。"""
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

    终版契约④（persona 锚点已注入时拓宽入口）：当 chat.py 已将 persona 的
    taste anchors 注入 `entities.cultural_likes`（用户跟随/直接点击了一个
    persona），即使问题文本不含显式推荐动词（如 "I want to get some books"、
    "给妈妈买件衣服"），也进入 Qloo 节点——种子里有 persona 锚点兜底，Qloo
    必然能解析并产出推荐。纯闲聊（hello/thanks/weather）除外。这保证
    "点击 persona 后怎么问都走 Qloo" 的预期，而不是让 fallback 误报
    "实体无法映射"。
    """
    if state.get("intent") == QLOO_INTENT:
        return "build_qloo_query"
    raw_query = str(state.get("raw_query", ""))
    if classify_intent(raw_query) == QLOO_INTENT:
        return "build_qloo_query"
    entities = state.get("entities") or {}
    likes = entities.get("cultural_likes") or []
    if isinstance(likes, list) and likes and not _looks_like_chitchat(raw_query):
        # persona 锚点已在种子列表：交给 Qloo 节点用锚点接地（mixed 模式仍会
        # 合并 message likes，locked 模式只读 persona 锚点）。
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
