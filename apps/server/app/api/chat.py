from __future__ import annotations

import re
from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/chat", tags=["chat"])

# ===== Qloo grounding: lightweight cultural-like extraction (no LLM, no NLP deps) =====
_LIKE_PATTERN = re.compile(
    r"(?:love|loves|like|likes|enjoy|enjoys|fan of|into)\s+([^.!?。！？\n;]{2,})",
    re.IGNORECASE,
)
_CLAUSE_STARTERS = re.compile(
    r"\b(but|where|what|how|who|which|when|because|needs?|would|can|to|that)\b",
    re.IGNORECASE,
)


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


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User input message")
    mode: str = Field(default="default", description="Agent mode")
    system_context: dict[str, Any] | None = Field(default=None)
    voice_context: dict[str, Any] | None = Field(default=None)
    conversation_id: int | None = Field(default=None)
    role_prompt: str | None = Field(default=None)


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

    user_prompt = payload.message
    if payload.system_context:
        user_prompt += f"\n\n[System Context]\n{payload.system_context}"

    system_prompt = CULTURAL_RECOMMENDATION_SYSTEM_PROMPT

    if not provider.enabled:
        reply = (
            "I'm running in preview mode — no LLM API key is configured, so I can't "
            "generate a live reply yet. Set LLM_API_KEY to enable culturally grounded "
            "answers from the Qloo taste graph."
        )
        return ChatResponse(reply=reply, taste_data_source="preview")

    # ---- Live grounding: resolve cultural likes against the Qloo taste graph ----
    taste_entities: list[str] = []
    taste_data_source = ""
    qloo_context: Any = None
    try:
        from app.services.qloo.client import get_qloo_client

        client = get_qloo_client()
        if client.enabled:
            likes = _extract_cultural_likes(payload.message)
            hits = await _collect_grounded_entities(client, likes, max_entities=3)
            if hits:
                taste_context = _format_grounding_context(hits)
                injected = CULTURAL_CONTEXT_INJECTION.format(qloo_context=taste_context)
                user_prompt = f"{injected.strip()}\n\n{user_prompt}"
                taste_entities = [h.get("name", "") for h in hits if h.get("name")]
                taste_data_source = "live"
                qloo_context = taste_context
    except Exception:
        taste_entities, taste_data_source, qloo_context = [], "", None

    result = await provider.chat(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.2,
        task_type="qloo_cultural_recommendation",
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
    from app.services.qloo.feedback import get_disliked_taste_names, get_liked_taste_names, record_feedback

    client = get_qloo_client()
    record = record_feedback(payload.message_id, payload.thumb, payload.taste_entities)
    live = client.enabled
    return FeedbackResponse(
        ok=True,
        message_id=record["message_id"],
        thumb=record["thumb"],
        data_source="live" if live else "preview",
        qloo_enabled=live,
        recorded=True,
        note=None if live else "Preview feedback recorded in memory only (no QLOO_API_KEY).",
        liked_taste_names=sorted(get_liked_taste_names()) if live else [],
        disliked_taste_names=sorted(get_disliked_taste_names()) if live else [],
    )