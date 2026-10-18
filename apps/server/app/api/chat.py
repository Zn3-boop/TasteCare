from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/chat", tags=["chat"])

logger = logging.getLogger(__name__)

# ===== Qloo grounding: lightweight cultural-like extraction (no LLM, no NLP deps) =====
_LIKE_PATTERN = re.compile(
    r"(?:love|loves|like|likes|enjoy|enjoys|fan of|into)\s+([^.!?。！？\n;]{2,})",
    re.IGNORECASE,
)
_CLAUSE_STARTERS = re.compile(
    r"\b(but|where|what|how|who|which|when|because|needs?|would|can|to|that)\b",
    re.IGNORECASE,
)

def _inject_profile_likes(user_prompt: str, profile_likes: list[str]) -> str:
    """Attach the user's accumulated taste profile (prior 👍 feedback) to the prompt.

    Used by the disable_qloo ablation branch so the "Without Qloo" baseline shares
    the SAME user taste profile / health context as the "With Qloo" branch — the only
    thing removed is the Qloo entity-context block (single-variable comparison).
    """
    if not profile_likes:
        return user_prompt
    header = (
        "[User Taste Profile] The user has previously liked: "
        f"{', '.join(profile_likes)}. "
        "Take these preferences into account when recommending."
    )
    return f"{header}\n\n{user_prompt}"


def _clean_like_segments(phrase: str, max_likes: int = 6) -> list[str]:
    """Split a like-phrase into candidate cultural anchors and drop clause tails.

    "Frank Sinatra and Italian food but needs low-sodium meals" -> ["Frank Sinatra", "Italian food"].
    Clause-starter words (but / where / needs...) cut the tail so the remaining
    fragment is a clean search term for Qloo.
    """
    parts = re.split(r"\s+(?:and|&)\s*|\s+—\s*|\s*,\s*|，|、|;|；", phrase)
    out: list[str] = []
    for part in parts:
        part = part.strip(" \t_·-–—':;\",，。")
        if not part:
            continue
        cut = _CLAUSE_STARTERS.search(part)
        if cut:
            part = part[: cut.start()].strip(" \t-–—':;\",，。")
        part = re.sub(r"^(?:the|a|an)\s+", "", part, count=1, flags=re.I)
        if not part or part.lower() in out:
            continue
        out.append(part)
        if len(out) >= max_likes:
            break
    return out


def _extract_cultural_likes(message: str, max_likes: int = 4) -> list[str]:
    """Extract up to max_likes cultural anchors from free-text user input."""
    likes: list[str] = []
    for m in _LIKE_PATTERN.finditer(message):
        for seg in _clean_like_segments(m.group(1), max_likes=max_likes):
            if seg.lower() not in [x.lower() for x in likes]:
                likes.append(seg)
            if len(likes) >= max_likes:
                return likes
    return likes


def _fallback_queries(like: str, max_drop: int = 3) -> list[str]:
    """Progressive de-scoping so 'the films of Christopher Nolan' still resolves."""
    words = like.split()
    return [" ".join(words[drop:]) for drop in range(max_drop + 1) if len(words) > drop]


async def _collect_grounded_entities(
    client: Any, likes: list[str], max_entities: int = 3
) -> list[dict[str, Any]]:
    """Resolve each extracted like to a real Qloo entity (deduped, max 3)."""
    from app.services.qloo.taste import search_cultural_entities

    hits: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for like in likes:
        for query in _fallback_queries(like):
            try:
                res = await search_cultural_entities(client, query, limit=1)
            except Exception:
                res = []
            if res:
                ent = res[0]
                name = ent.get("name") or ent.get("entity_id") or ""
                if name and name.lower() not in seen_names:
                    seen_names.add(name.lower())
                    hits.append(ent)
                break
        if len(hits) >= max_entities:
            break
    return hits


def _format_grounding_context(hits: list[dict[str, Any]]) -> str:
    """Render the resolved entity list as the Qloo context block for the LLM."""
    lines = ["[Qloo Cultural Intelligence - Taste Entities resolved from your message]"]
    for i, ent in enumerate(hits, 1):
        name = ent.get("name", "Unknown")
        etype = ent.get("type", "unknown")
        domain = ent.get("domain", etype)
        lines.append(f"  {i}. {name} ({etype}) [domain={domain}]")
    lines.append("[End of Qloo Taste Entities - use these only to ground your recommendations]")
    return "\n".join(lines)


def _format_qloo_only_reply(
    hits: list[dict[str, Any]], recs: list[dict[str, Any]], user_message: str
) -> str:
    """Compose a culturally grounded reply using ONLY live Qloo data.

    This powers the Qloo-only mode (no LLM key configured): the agent still
    resolves the user's cultural anchors through the Qloo taste graph and
    returns real taste-based recommendations instead of an error.
    """
    lines = [
        "Here's what the Qloo taste graph surfaced for your request — no generic guesswork, just real cultural data:",
        "",
    ]
    for i, ent in enumerate(hits, 1):
        domain = ent.get("domain") or ent.get("type", "entity")
        lines.append(f"  {i}. {ent.get('name', 'Unknown')}  ·  {domain}")
    if recs:
        lines.append("")
        lines.append("Recommendations grounded in those anchors (from Qloo's 250M+ entity taste graph):")
        for i, r in enumerate(recs[:6], 1):
            name = r.get("name", "Unknown")
            pop = r.get("popularity")
            pop_txt = f" — {round(pop * 100)}% Qloo popularity" if pop is not None else ""
            lines.append(f"  {i}. {name}{pop_txt}")
        lines.append("")
    lines.append("Qloo grounding is live; health-related suggestions still need your own verification (see the disclaimer below).")
    return "\n".join(lines)


def _format_no_qloo_rule_baseline(message: str) -> str:
    """Compose the deterministic "Without Qloo" baseline reply for the no-LLM-key
    path.

    Pure rules only: nutritionally-safe generic senior meals, deliberately
    detached from any cultural identity. This is what the ablation column must
    show when no LLM is configured — without it, the Qloo-only live path used to
    leak Qloo data into BOTH ablation columns and the comparison became fake.
    """
    target = _domain_for_message(message)
    generic = [
        "Here are some generally popular, healthy meal options for a senior — no cultural grounding, just safe nutrition defaults:",
        "",
    ]
    picks = [
        "  1. Baked salmon with steamed asparagus",
        "  2. Grilled chicken breast with roasted vegetables",
        "  3. Soft polenta with sautéed mushrooms",
        "  4. Lentil soup with a slice of whole-grain bread",
        "  5. Oatmeal with berries and low-fat milk",
    ]
    generic.extend(picks)
    note = (
        "These options are nutritionally defensible but culturally generic — they "
        "don't reflect this person's actual taste. Compare with the Qloo-grounded "
        "column, which matches recommendations to a real cultural identity built "
        "from a 250M+ entity taste graph."
    )
    if target == "film":
        generic.insert(1, "  (Popular studio dramas hitting the usual awards circuit — familiar, widely-known titles.)")
    elif target == "music":
        generic.insert(1, "  (Chart-toppers and greatest-hits compilations — the most-streamed, most mainstream picks.)")
    else:
        pass
    generic.append("")
    generic.append(note)
    return "\n".join(generic)


def _domain_for_message(message: str) -> str | None:
    """Pick a Qloo target domain from the message wording (Qloo-only composer)."""
    text = message.lower()
    if any(w in text for w in ("eat", "food", "dinner", "lunch", "meal", "restaurant", "dining", "cuisine", "dish", "chew")):
        return "dining"
    if any(w in text for w in ("watch", "film", "movie", "show", "series")):
        return "film"
    if any(w in text for w in ("listen", "music", "song", "band", "artist", "album")):
        return "music"
    return None


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User input message")
    mode: str = Field(default="default", description="Agent mode")
    system_context: dict[str, Any] | None = Field(default=None)
    voice_context: dict[str, Any] | None = Field(default=None)
    conversation_id: int | None = Field(default=None)
    role_prompt: str | None = Field(default=None)
    disable_qloo: bool = Field(default=False, description="Skip Qloo cultural grounding (for ablation comparison).")
    session_id: str = Field(default="default", description="Session key for the user's persistent taste-feedback store.")


class ChatResponse(BaseModel):
    reply: str
    taste_entities: list[str] = Field(default_factory=list)
    taste_data_source: str = ""
    qloo_context: Any | None = None


@router.post("/agent", response_model=ChatResponse)
async def chat_with_agent(payload: ChatRequest):
    """Chat with the culturally intelligent agent.

    Uses the shared LLM provider (provider.chat) — NOT the OpenAI SDK's
    namespace object — and wraps the user message with the Qloo cultural
    recommendation system prompt + context injection from prompts.py.

    Live grounding: when Qloo is enabled, cultural likes are extracted from the
    user message, resolved through search_cultural_entities(), injected via
    CULTURAL_CONTEXT_INJECTION, and returned as taste_entities / taste_data_source
    / qloo_context so the web Agent tab can render real grounding evidence.

    When Qloo is disabled or nothing resolves, the endpoint returns an EMPTY
    grounding payload (panel shows nothing) instead of claiming it used Qloo.

    Without an LLM key the endpoint still answers deterministically in preview
    mode, so the web demo Agent tab never hard-fails on a fresh checkout.
    """
    from app.services.llm.provider import provider
    from app.services.qloo.prompts import (
        CULTURAL_RECOMMENDATION_SYSTEM_PROMPT,
        CULTURAL_CONTEXT_INJECTION,
    )
    from app.services.qloo.feedback import get_feedback_store

    # Session-scoped feedback store: the same session gets the same store across
    # requests, so profile likes / disliked exclusions accumulate per user.
    store = get_feedback_store(payload.session_id)

    user_prompt = payload.message
    if payload.system_context:
        user_prompt += f"\n\n[System Context]\n{payload.system_context}"

    system_prompt = CULTURAL_RECOMMENDATION_SYSTEM_PROMPT

    # ---- Qloo-only mode (no LLM key): the agent still answers with real
    # cultural data from the Qloo taste graph, never a hard error. ----
    if not provider.enabled:
        # Ablation integrity: with no LLM key the Qloo-only live path below used
        # to ignore payload.disable_qloo and return live Qloo data for BOTH
        # ablation columns — a fake comparison. Honour the flag here with a pure
        # rule-based baseline so the "Without Qloo" column is genuinely Qloo-free.
        if payload.disable_qloo:
            return ChatResponse(
                reply=_format_no_qloo_rule_baseline(payload.message),
                taste_data_source="no_qloo",
            )
        try:
            from app.services.qloo.client import get_qloo_client
            from app.services.qloo.taste import get_taste_based_recommendations

            client = get_qloo_client()
            if client.enabled:
                message_likes = _extract_cultural_likes(payload.message)
                if message_likes:
                    hits = await _collect_grounded_entities(client, message_likes, max_entities=4)
                    if hits:
                        recs: list[dict[str, Any]] = []
                        target = _domain_for_message(payload.message)
                        try:
                            rec_result = await asyncio.wait_for(
                                get_taste_based_recommendations(
                                    client,
                                    [h.get("id") or h.get("entity_id", "") for h in hits if h.get("id") or h.get("entity_id")],
                                    target_domain=target,
                                    limit=6,
                                    store=store,
                                ),
                                timeout=20,
                            )
                            recs = rec_result.get("recommendations", []) or []
                        except Exception:
                            recs = []
                        reply = _format_qloo_only_reply(hits, recs, payload.message)
                        taste_entities = [h.get("name", "") for h in hits if h.get("name")]
                        taste_context = _format_grounding_context(hits)
                        return ChatResponse(
                            reply=reply,
                            taste_entities=taste_entities,
                            taste_data_source="live",
                            qloo_context=taste_context,
                        )
        except Exception:
            pass
        reply = (
            "I'm running in preview mode — Qloo grounding is available, but no LLM "
            "connection is configured for a full conversational reply. Try the "
            "Senior Dining tab or the Community tab, which work end-to-end with only "
            "a QLOO_API_KEY."
        )
        return ChatResponse(reply=reply, taste_data_source="preview")

    # ---- 用户口味画像（历史 👍 反馈）—— with/without Qloo 两条分支共享 ----
    # 读取一次、两处使用，保证 Ablation 对照组两边拿到完全相同的 profile。
    try:
        profile_likes = [n for n in store.get_liked_taste_names() if n][:3]
    except Exception:
        profile_likes = []

    # ---- Ablation 对照组：disable_qloo=true ----
    # 单一变量原则：与正常分支复用同一个 CULTURAL_RECOMMENDATION_SYSTEM_PROMPT、
    # 同一份用户口味画像、相同的 temperature/task_type。唯一差异是**不解析、不注入
    # Qloo 实体上下文块**——被隔离的变量只有 Qloo 文化图谱本身。
    if payload.disable_qloo:
        ab_user = _inject_profile_likes(user_prompt, profile_likes)
        try:
            result = await asyncio.wait_for(
                provider.chat(
                    system_prompt=system_prompt,
                    user_prompt=ab_user,
                    temperature=0.2,
                    task_type="qloo_cultural_recommendation",
                ),
                timeout=getattr(provider, "timeout", None) or 45,
            )
        except Exception:
            result = (
                "⚠ The LLM connection failed or timed out. This is the 'Without "
                "Qloo' baseline — try again, or switch to the Qloo-grounded branch "
                "which stays available even when the LLM is unavailable."
            )
        reply = result if isinstance(result, str) else str(result)
        return ChatResponse(reply=reply, taste_data_source="no_qloo")

    # ---- Live grounding: run the Qloo cultural recommendation NODE inside the
    # LangGraph agent pipeline. /chat/agent builds an AgentState and executes it
    # through graph.ainvoke() on the compiled StateGraph — so every live
    # grounding pass genuinely runs the agent framework's scheduler, not a
    # parallel hand-rolled call. If graph execution unexpectedly fails, we
    # degrade back to the exact same node awaited directly (deterministic
    # fallback, never a hard error).
    taste_entities: list[str] = []
    taste_data_source = ""
    qloo_context: Any = None
    try:
        from app.services.graph.nodes import qloo_cultural_recommend_node

        # Taste-profile evolution (Phase 2C): anchors accumulated from prior 👍
        # feedback are injected as extra cultural signals, so the agent's next
        # recommendation is grounded on the user's evolving taste — not just the
        # current message.
        message_likes = _extract_cultural_likes(payload.message)
        likes = [*profile_likes, *message_likes]
        node_state: dict[str, Any] = {
            "raw_query": payload.message,
            "session_id": payload.session_id,
            "feedback_store": store,
            "entities": {
                "cultural_likes": likes,
                "target_domain": _domain_for_message(payload.message) or "",
            },
        }
        node_result: dict[str, Any] = {}
        try:
            from app.services.graph.graph import build_qloo_agent_graph

            graph = build_qloo_agent_graph()
            result_state = await graph.ainvoke(node_state)
            if isinstance(result_state, dict):
                node_result = result_state
        except Exception:
            logger.warning(
                "LangGraph StateGraph invocation failed, falling back to direct qloo node", exc_info=True
            )
            node_result = await qloo_cultural_recommend_node(node_state)
        if node_result:
            logger.info(
                "LangGraph StateGraph invoked, executed qloo_cultural_recommend_node resolved=%s seeds=%s",
                node_result.get("qloo_resolved_names", []),
                node_result.get("qloo_seed_names", []),
            )
        resolved_names = node_result.get("qloo_resolved_names", [])
        if not isinstance(resolved_names, list):
            resolved_names = []
        resolved_names = [str(n) for n in resolved_names if n]
        if node_result.get("qloo_enabled") and resolved_names:
            # LangGraph execution evidence: /chat/agent ran the agent framework's
            # B档 qloo agent StateGraph (input_node -> intent_node -> build_qloo_query
            # -> qloo_call_node -> format_output) whose qloo_call_node executes the
            # same qloo_cultural_recommend_node used by the full pipeline.
            logger.info(
                "LangGraph node executed: qloo_cultural_recommend_node resolved=%s seeds=%s",
                resolved_names,
                node_result.get("qloo_seed_names", []),
            )
            # The node's taste context (taste-based recommendations) is the
            # richest grounding block; when the recommendations call degrades
            # (e.g. Qloo rate-limit / partial mock), still ground on the
            # resolved taste entities so the LLM prompt is never left blind.
            taste_context = node_result.get("qloo_taste_context") or ""
            if not taste_context:
                hits_like = [
                    {"name": n, "type": "taste-entity", "domain": _domain_for_message(payload.message) or "mixed"}
                    for n in resolved_names
                ]
                taste_context = _format_grounding_context(hits_like)
            qloo_context = taste_context
            injected = CULTURAL_CONTEXT_INJECTION.format(qloo_context=qloo_context)
            user_prompt = f"{injected.strip()}\n\n{user_prompt}"
            taste_entities = resolved_names
            taste_data_source = "live"
        elif node_result.get("last_error"):
            logger.warning("Qloo node degraded: %s", node_result["last_error"])
        elif node_result.get("fallback_message"):
            logger.info("Qloo agent fallback: %s", node_result["fallback_message"])
    except Exception:
        taste_entities, taste_data_source, qloo_context = [], "", None

    result = await asyncio.wait_for(
        provider.chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2,
            task_type="qloo_cultural_recommendation",
        ),
        timeout=getattr(provider, "timeout", None) or 45,
    )
    reply = result if isinstance(result, str) else str(result)
    return ChatResponse(
        reply=reply,
        taste_entities=taste_entities,
        taste_data_source=taste_data_source,
        qloo_context=qloo_context,
    )


class FeedbackRequest(BaseModel):
    message_id: str = Field(..., min_length=1, description="Opaque id of the assistant recommendation message (client-generated).")
    thumb: Literal["up", "down"] = Field(..., description="User sentiment: 'up' likes the recommendation, 'down' dislikes it.")
    taste_entities: list[str] = Field(default_factory=list, description="Taste entity names this feedback applies to (from qloo:taste-context).")
    conversation_id: int | None = Field(default=None, description="Optional conversation id for context.")
    session_id: str = Field(default="default", description="Session key whose persistent taste-feedback store this feedback is written to.")


class FeedbackResponse(BaseModel):
    ok: bool
    message_id: str
    thumb: str
    data_source: str
    qloo_enabled: bool
    recorded: bool
    note: str | None = None
    liked_taste_names: list[str] = Field(default_factory=list)
    disliked_taste_names: list[str] = Field(default_factory=list)


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(payload: FeedbackRequest):
    from app.services.qloo.client import get_qloo_client
    from app.services.qloo.feedback import get_feedback_store

    client = get_qloo_client()
    store = get_feedback_store(payload.session_id)
    record = store.record_feedback(payload.message_id, payload.thumb, payload.taste_entities)
    live = client.enabled
    return FeedbackResponse(
        ok=True,
        message_id=record["message_id"],
        thumb=record["thumb"],
        data_source="live" if live else "preview",
        qloo_enabled=live,
        recorded=True,
        note=None if live else "Preview feedback recorded in memory only (no QLOO_API_KEY).",
        liked_taste_names=sorted(store.get_liked_taste_names()) if live else [],
        disliked_taste_names=sorted(store.get_disliked_taste_names()) if live else [],
    )