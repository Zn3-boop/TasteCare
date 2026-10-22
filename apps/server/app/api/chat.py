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


def _extract_plain_list_likes(message: str, max_likes: int = 6) -> list[str]:
    """Extract cultural anchors from a comma-separated plain list (no like verb).

    "classic Chicago blues, mid-century modern design, craft jazz vinyl records"
    -> ["classic Chicago blues", "mid-century modern design", "craft jazz vinyl records"].

    The list must be bare (2+ items, no leading like verb) so sentences such as
    "I like jazz" still route through `_LIKE_PATTERN` and don't over-split.
    Clause-starter words (but / where / what / to / give me / about...) cut the
    tail so trailing requests like ",give me an advice about book" don't leak a
    whole clause into the seed list.
    """
    msg = (message or "").strip()
    # Only treat as a plain list when there are at least 2 comma separators.
    if msg.count(",") < 2 and msg.count("，") < 2 and msg.count("、") < 2:
        return []
    # Drop trailing clause-starter tails (give me / show me / tell me / how about)
    # BEFORE splitting so a trailing request never becomes a bogus anchor.
    msg = re.sub(
        r"(?:\b(give|show|tell|help|recommend|suggest|advise)\s+(?:me|us)?\s*(?:an?|some)?\s*(?:advice|idea|ideas|tip|tips|recommendation|recommendations)?\b.*)$",
        "",
        msg,
        flags=re.IGNORECASE,
    )
    msg = msg.strip(" \t_·-–—':;\",，。")
    if not msg:
        return []
    parts = re.split(r"\s*,\s*|\s*，\s*|\s*、\s*", msg)
    out: list[str] = []
    for part in parts:
        part = part.strip(" \t_·-–—':;\",，。")
        if not part or len(part) < 2:
            continue
        # A clause starter in the middle (but/where/what/how) means this part is
        # not a plain anchor — drop the remainder of the list.
        if _CLAUSE_STARTERS.search(part):
            break
        part = re.sub(r"^(?:the|a|an)\s+", "", part, count=1, flags=re.I)
        if part.lower() in out:
            continue
        out.append(part)
        if len(out) >= max_likes:
            break
    return out


def _extract_cultural_likes(message: str, max_likes: int = 4) -> list[str]:
    """Extract up to max_likes cultural anchors from free-text user input.

    Supports both verb-led phrases ("I love Frank Sinatra", "I enjoy jazz")
    and bare comma-separated lists ("classic Chicago blues, jazz, vinyl") so a
    Qloo-only (no-LLM) pipeline still gets anchors from the full range of demo
    inputs.
    """
    likes: list[str] = []
    for m in _LIKE_PATTERN.finditer(message):
        for seg in _clean_like_segments(m.group(1), max_likes=max_likes):
            if seg.lower() not in [x.lower() for x in likes]:
                likes.append(seg)
            if len(likes) >= max_likes:
                return likes
    if likes:
        return likes
    # No like verb — try the bare comma-separated list extraction so pure
    # "A, B, C, give me advice about X" inputs still resolve to anchors.
    for seg in _extract_plain_list_likes(message, max_likes=max_likes):
        if seg.lower() not in [x.lower() for x in likes]:
            likes.append(seg)
        if len(likes) >= max_likes:
            return likes
    return likes


def _persona_anchor_likes(persona_anchors: str | None, max_likes: int = 6) -> list[str]:
    """Split the active persona's comma-separated taste anchors into clean seeds.

    The web persona profile stores anchors as free text ("Frank Sinatra, Jazz,
    Italian cuisine"), so this parser is deliberately lightweight: split on
    commas, drop empties, dedupe case-insensitively. These anchors are merged
    AHEAD of message-derived likes so the agent is genuinely bound to the
    current persona (the "🔗 Bound to Maria" badge) instead of only grounding on
    whatever phrase the current message happens to contain.
    """
    if not persona_anchors:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for raw in re.split(r"[，,、;；]+", persona_anchors):
        name = raw.strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(name)
        if len(out) >= max_likes:
            break
    return out


def _persona_binding_note(
    bound: bool,
    persona_name: str | None,
    persona_anchors: str | None,
) -> str:
    """System-level annotation describing the current persona-binding state.

    Appended to the system prompt by /chat/agent so the LLM's OUTPUT contract
    matches what was actually grounded:
      • Bound person  — the ONLY taste source is the persona's saved anchors
        (captured when the profile was first created, i.e. the 习惯爱好 field).
        Recommend from these anchors; never demand the user restate their own
        habits or tastes.
      • No bound person — there are NO saved anchors. If the request already
        lacks both concrete likes and a concrete need, the agent must ASK the
        user for their 习惯爱好 (likes/habits) and 需求 (need) before picking
        anything — never invent tastes on the user's behalf.
    """
    name = (persona_name or "").strip()
    anchors = _persona_anchor_likes(persona_anchors)
    if bound:
        header = (
            "\n[Persona Binding State] persona_bound: True\n"
            f"Persona: {name or '(unnamed persona profile)'}\n"
            f"Injected tastes (from the persona's saved profile ONLY): "
            f"{', '.join(anchors) if anchors else '(none saved yet)'}\n\n"
            "Output requirement: the user is represented by this bound persona. "
            "Ground EVERY recommendation ONLY on the persona's saved taste anchors "
            "above (its 习惯爱好 / taste profile, set when the person was created). "
            "Do NOT ask the user to state their own habits or tastes again — "
            "answer their current request directly from these anchors."
        )
    else:
        header = (
            "\n[Persona Binding State] persona_bound: False\n"
            "Injected tastes: none (no persona profile is bound to this session).\n\n"
            "Output requirement: there are no saved taste anchors. If the user's "
            "request does not already state BOTH their 习惯爱好 (cultural likes / "
            "habits) AND a concrete 需求 (what they need, e.g. a music/film/book/"
            "meal/destination ask), FIRST ask one short question requesting both. "
            "Never invent tastes on the user's behalf."
        )
    return header


def _priority_order_seeds(
    persona_likes: list[str],
    message_likes: list[str],
    core_anchors: list[str],
    exclude_seeds: tuple[str, ...] | None = None,
    exclude_keywords: tuple[str, ...] | None = None,
) -> list[str]:
    """Assemble taste seeds by the persona-first priority rule.

    Priority: bound-persona anchors (+ accumulated 👍 feedback) > current-query
    likes; the fixed core fallback anchors (Chicago blues / MCM design / craft
    jazz vinyl) are used ONLY when there is nothing else — an unbound session
    with no message likes still gets SOME grounding. A bound persona's own
    tastes are the ONLY legitimate first-class seeds: the generic core trio
    must never appear alongside a bound persona's profile (fix 单 §五
    "绑定人物时绝不允许那三条出现"). Anything matching the explicit exclude
    list (exact seed or class keyword) is dropped.
    """
    if exclude_seeds is None:
        exclude_seeds = _QLOO_EXCLUDE_SEEDS
    if exclude_keywords is None:
        exclude_keywords = _QLOO_EXCLUDE_KEYWORDS
    out: list[str] = []
    seen: set[str] = set()
    for like in [*persona_likes, *message_likes]:
        name = (like or "").strip()
        if not name or name.lower() in seen:
            continue
        if _seed_is_excluded(name, exclude_seeds, exclude_keywords):
            continue
        seen.add(name.lower())
        out.append(name)
    # Fixed generic core anchors: absolute last resort only when nothing else
    # exists (unbound session + no message likes). With a bound persona (or any
    # message likes) they are entirely omitted — never shadow the persona.
    if not out:
        for like in core_anchors:
            name = (like or "").strip()
            if not name or name.lower() in seen:
                continue
            if _seed_is_excluded(name, exclude_seeds, exclude_keywords):
                continue
            seen.add(name.lower())
            out.append(name)
    return out


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
    """Render the resolved entity list as the Qloo context block for the LLM.

    Every entity carries its Qloo match score / popularity when Qloo provided one
    so the grounding evidence is *score-visible* (the "92% → Tony Bennett" style
    proof the demo needs). Scores are never fabricated: when a normalized entity
    has neither `score` nor `popularity`, we omit the score column instead of
    inventing one.
    """
    lines = ["[Qloo Cultural Intelligence - Taste Entities resolved from your message]"]
    for i, ent in enumerate(hits, 1):
        name = ent.get("name", "Unknown")
        etype = ent.get("type", "unknown")
        domain = ent.get("domain", etype)
        score = ent.get("score")
        if score is None:
            score = ent.get("popularity")
        score_txt = f" [match={round(float(score) * 100):.0f}%]" if isinstance(score, (int, float)) else ""
        lines.append(f"  {i}. {name} ({etype}) [domain={domain}]{score_txt}")
    lines.append("[End of Qloo Taste Entities - use these only to ground your recommendations]")
    return "\n".join(lines)


# Geographic consistency guard for dining recommendations.
#
# The shared recommendation path passes filter.location.query to Qloo, but the
# returned place entities do not all carry machine-readable location metadata
# (Qloo's /v2/insights does not expose city on every entity). Before presenting a
# dining venue as *grounded evidence for the user's requested city*, we verify
# the venue name carries at least one city/region token from the requested
# location — otherwise the demo could show an "all-Chicago list" for a New York
# request and present it as proof. This is the contract's hard rule: **位置错配就
# 报错，绝不硬编兜底** — a mismatch is reported as such, never silently patched.
_LOCATION_CITY_TOKENS: dict[str, tuple[str, ...]] = {
    "New York": ("new york", "nyc", "manhattan", "brooklyn", "queens", "bronx", "staten island", "new york city"),
    "Boston": ("boston", "cambridge", "somerville", "brookline"),
    "Chicago": ("chicago", "the loop", "river north"),
    "Los Angeles": ("los angeles", "la", "hollywood", "santa monica", "west hollywood"),
    "San Francisco": ("san francisco", "sf", "bay area", "oakland", "berkeley"),
    "Seattle": ("seattle", "bellevue", "tacoma"),
    "Miami": ("miami", "miami beach", "coral gables"),
    "Austin": ("austin"),
    "Atlanta": ("atlanta"),
    "Philadelphia": ("philadelphia", "philly"),
    "Washington DC": ("washington", "dc", "washington dc"),
    "London": ("london"),
    "Paris": ("paris"),
    "Berlin": ("berlin"),
    "Toronto": ("toronto"),
    "Tokyo": ("tokyo"),
    "Shanghai": ("shanghai"),
    "Beijing": ("beijing"),
    "Hong Kong": ("hong kong"),
    "Singapore": ("singapore"),
    "Sydney": ("sydney"),
}


def _entity_matches_location(ent: dict[str, Any], location: str | None) -> bool | None:
    """Return whether a recommendation entity plausibly belongs to `location`.

    Returns:
      True  — the entity name (or its location tags) contains a token of the city.
      False — the entity is a dining venue and NO requested-city token is present.
      None  — not applicable (no location requested, or entity has no location
              metadata worth judging). Callers must treat None as "keep".

    The conservative default matters: we only *hard-reject* dining places when we
    can't find any city signal, so a venue name like "Tony's Steakhouse NYC" is
    kept while "Mott Street Tavern" (no city) is flagged for the mismatch report.
    """
    if not location:
        return None
    loc = location.strip()
    tokens = _LOCATION_CITY_TOKENS.get(loc, (loc.lower(),))
    text_parts: list[str] = []
    for key in ("name", "city", "location", "address"):
        val = ent.get(key)
        if isinstance(val, str):
            text_parts.append(val)
    for tag in ent.get("tags") or []:
        if isinstance(tag, str):
            text_parts.append(tag)
    blob = " ".join(text_parts).lower()
    if any(t in blob for t in tokens):
        return True
    return False


def _verify_dining_location(
    recommendations: list[dict[str, Any]],
    location: str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split recommendations into (location_verified, mismatch_reported).

    Dining venues with no city signal are *reported* as mismatched (never silently
    dropped from the reply — the user must see the honest status), while non-dining
    entities are kept regardless. This keeps the "show the process" principle:
    mismatches surface as status, not as hidden data loss.
    """
    if not location:
        return recommendations, []
    verified: list[dict[str, Any]] = []
    mismatched: list[dict[str, Any]] = []
    for ent in recommendations:
        result = _entity_matches_location(ent, location)
        if result is False:
            mismatched.append(ent)
        else:
            verified.append(ent)
    return verified, mismatched


# ===== Qloo structured-guided template (7 categories: music/film/dining/fashion/travel/podcast/book) =====
# Priority rule enforced at seed-assembly time: current-query seeds > fixed core
# anchors > stored historical seeds. The explicit exclude list blocks off-theme
# drift (stale Italian pop / old persona anchors, e.g. "Fellini's Casanova"
# leaking out of an earlier persona) from ever re-entering the signal list; the
# result-side keywords keep the "all Italian pop/rap artists" CLASS exclusion
# without fabricating a category-URN list.
_QLOO_CORE_ANCHORS: tuple[str, ...] = (
    "classic Chicago blues",
    "mid-century modern design",
    "craft jazz vinyl records",
)
_QLOO_EXCLUDE_SEEDS: tuple[str, ...] = (
    "Fellini's Casanova",
    "Croce Rossa Italiana - Comitato Regionale del Lazio",
    "Croce Rossa Italiana",
)
_QLOO_EXCLUDE_KEYWORDS: tuple[str, ...] = (
    "fellini",
    "lazio",
    "croce rossa",
    "italian pop",
    "italian rap",
)


def _seed_is_excluded(
    name: str,
    exact_seeds: tuple[str, ...] = (),
    keywords: tuple[str, ...] = (),
) -> bool:
    """True when a taste-seed / result name hits an explicit exclusion.

    Matches exact seed names, the seed names as substrings (so the long
    Red Cross committee name is caught by "croce rossa"), and whole-class
    keywords like "italian pop". Case-insensitive.
    """
    key = (name or "").strip().lower()
    if not key:
        return True
    if key in {e.strip().lower() for e in exact_seeds}:
        return True
    return any(
        e and len(e) >= 3 and e in key for e in exact_seeds
    ) or any(k and k in key for k in keywords)


_QLOO_DOMAIN_LABELS: dict[str, str] = {
    "film": "movie/film",
    "dining": "dining/eating",
    "music": "music",
    "fashion": "fashion",
    "travel": "travel",
    "podcast": "podcast",
    "book": "books/reading",
}


def _recommendation_reason(rec: dict[str, Any], seeds: list[dict[str, Any]], domain: str | None) -> str:
    """A short, HONEST reason for one recommendation — never a fabricated story.

    Priority:
      1. The entity's own Qloo description (real data), first sentence, capped.
      2. A transparent matching rationale: the rec shares its cultural domain
         with the anchor seeds Qloo's taste graph resolved them against. We
         state the mechanism (same domain adjacency in the taste graph), not an
         invented narrative about WHY the user would like it.
    """
    desc = rec.get("description")
    if isinstance(desc, str) and desc.strip():
        first = desc.strip().split("\n")[0].split(". ")[0].strip()
        return f"Qloo profile: {first[:140]}."
    anchor_names = [h.get("name", "") for h in seeds if h.get("name")]
    if anchor_names:
        anchors_txt = ", ".join(anchor_names[:2])
        label = _QLOO_DOMAIN_LABELS.get(domain or "", domain or "cultural")
        return f"Qloo's taste graph ranks it adjacent to your anchors ({anchors_txt}) in the {label} domain."
    label = _QLOO_DOMAIN_LABELS.get(domain or "", domain or "cultural")
    return f"Qloo's taste graph ranked it for your {label} interests."


def _format_qloo_only_reply(
    hits: list[dict[str, Any]],
    recs: list[dict[str, Any]],
    user_message: str,
    target_domain: str | None = None,
    persona_name: str | None = None,
) -> str:
    """Compose a culturally grounded reply using ONLY live Qloo data.

    This powers the Qloo-only mode (no LLM key configured): the agent still
    resolves the user's cultural anchors through the Qloo taste graph and
    returns real taste-based recommendations instead of an error.

    `target_domain` (the PRIMARY goal domain detected from the message) is
    surfaced explicitly up-front so the user always sees WHY the agent picked
    this kind of recommendation — especially when a preference seed ("I love
    food") and a request goal ("where should I watch a movie") point at
    different domains.

    The reply ALWAYS separates the resolved ANCHOR SEEDS (the user's/persona's
    taste anchors) from the actual RECOMMENDATIONS computed by Qloo's taste
    graph — the old wording listed `hits` under a "recommendations" heading, so
    a request like "which fashionable place can I go to" with only persona seeds
    resolved looked like the seeds themselves were the recommendations.
    """
    lines: list[str] = []
    if persona_name:
        lines.append(f"You're chatting as {persona_name} — recommendations below are grounded in that persona's taste profile.")
        lines.append("")
    if target_domain:
        label = _QLOO_DOMAIN_LABELS.get(target_domain, target_domain)
        likes_txt = ", ".join(ent.get("name", "") for ent in hits if ent.get("name")) or "what you like"
        lines.append(
            f"I detected your main ask is {label} recommendations. "
            f"I still used your taste preferences ({likes_txt}) as cultural seeds to match what you love."
        )
        lines.append("")
    if hits:
        lines.append("Cultural anchor seeds resolved from your taste profile (the 'what' behind every pick below):")
        for i, ent in enumerate(hits, 1):
            domain = ent.get("domain") or ent.get("type", "entity")
            score = ent.get("score")
            if score is None:
                score = ent.get("popularity")
            score_txt = f" — {round(float(score) * 100):.0f}% Qloo match" if isinstance(score, (int, float)) else ""
            lines.append(f"  {i}. {ent.get('name', 'Unknown')}  ·  {domain}{score_txt}")
        lines.append("")
    if recs:
        lines.append("Recommendations grounded in those anchors (from Qloo's 250M+ entity taste graph):")
        for i, r in enumerate(recs[:6], 1):
            name = r.get("name", "Unknown")
            pop = r.get("popularity")
            pop_txt = f" — {round(pop * 100)}% Qloo popularity" if pop is not None else ""
            lines.append(f"  {i}. {name}{pop_txt}")
            lines.append(f"     💡 {_recommendation_reason(r, hits, target_domain)}")
        lines.append("")
    else:
        lines.append(
            "Qloo did not return taste-graph recommendations for these seeds yet "
            "(try a more specific seed, or ask again after adding more taste anchors)."
        )
        lines.append("")
    # Matching logic — transparent, no LLM grounding, only Qloo taste graph
    # nearest-neighbor retrieval, so the user can verify how each pick was
    # derived from their anchors (not a black-box list).
    lines.append(
        "How this was matched (no LLM grounding — only Qloo taste graph nearest neighbor retrieval): "
        "I took your cultural anchors as seeds, asked Qloo's taste graph"
    )
    if target_domain:
        label = _QLOO_DOMAIN_LABELS.get(target_domain, target_domain)
        lines.append(f"for {label} entities ranked near those seeds, and ranked the results by Qloo popularity.")
    else:
        lines.append("for entities ranked near those seeds, and ranked the results by Qloo popularity.")
    lines.append("")
    lines.append("Qloo grounding is live; health-related suggestions still need your own verification (see the disclaimer below).")
    return "\n".join(lines)


def _format_no_qloo_rule_baseline(message: str) -> str:
    """Compose the deterministic "Without Qloo" baseline reply for the no-LLM-key
    path.

    Pure rules only: generic, culturally-neutral picks matched to the detected
    target domain (meal options for dining, chart-toppers for music, blockbusters
    for film, etc.), deliberately detached from any cultural identity. This is
    what the ablation column must show when no LLM is configured — without it,
    the Qloo-only live path used to leak Qloo data into BOTH ablation columns
    and the comparison became fake.
    """
    target = _domain_for_message(message)
    domain_picks: dict[str, tuple[str, tuple[str, ...]]] = {
        "dining": (
            "some generally popular, healthy meal options for a senior — no cultural grounding, just safe nutrition defaults",
            (
                "  1. Baked salmon with steamed asparagus",
                "  2. Grilled chicken breast with roasted vegetables",
                "  3. Soft polenta with sautéed mushrooms",
                "  4. Lentil soup with a slice of whole-grain bread",
                "  5. Oatmeal with berries and low-fat milk",
            ),
        ),
        "film": (
            "compact, widely-known drama films — familiar titles, no cultural specificity",
            (
                "  1. A quiet character drama about family and forgiveness",
                "  2. A courtroom drama with a celebrated ensemble cast",
                "  3. A small-town coming-of-age story",
                "  4. A literary adaptation with strong reviews",
                "  5. A feel-good comedy with a veteran cast",
            ),
        ),
        "music": (
            "chart-toppers and greatest-hits compilations — the most-streamed, most mainstream picks",
            (
                "  1. Today's top-streamed pop single",
                "  2. A classic-rock greatest hits compilation",
                "  3. A smooth jazz standards album",
                "  4. Contemporary easy-listening radio hits",
                "  5. A well-known orchestral classics disc",
            ),
        ),
        "fashion": (
            "safe, widely-available style staples — classic cuts with broad appeal",
            (
                "  1. Classic navy blazer and tailored chinos",
                "  2. Comfortable knitwear in neutral tones",
                "  3. Smart casual button-down with dark denim",
                "  4. Versatile trench coat for transitional weather",
                "  5. Polished leather loafers",
            ),
        ),
        "travel": (
            "popular, well-trodden destinations with broad appeal — no personal taste matching",
            (
                "  1. A familiar coastal resort town",
                "  2. A classic European capital city break",
                "  3. A countryside retreat known for scenery",
                "  4. An all-inclusive beach hotel",
                "  5. A guided bus tour of a historic city",
            ),
        ),
        "podcast": (
            "the biggest, most-subscribed shows across general categories",
            (
                "  1. A top-rated true-crime series",
                "  2. A widely-followed daily news briefing",
                "  3. A celebrity-interview flagship",
                "  4. A mainstream self-improvement show",
                "  5. A history narrative with huge listener counts",
            ),
        ),
        "book": (
            "bestseller-list staples — widely sold titles with mainstream appeal",
            (
                "  1. A recent bestselling mystery novel",
                "  2. A popular narrative nonfiction history",
                "  3. A critically-acclaimed literary fiction title",
                "  4. A well-known biography of a public figure",
                "  5. A broad overview of a popular science topic",
            ),
        ),
    }
    if target and target in domain_picks:
        intro, picks = domain_picks[target]
    else:
        intro, picks = domain_picks["dining"]
    generic = [f"Here are {intro}:"]
    generic.extend([""])
    generic.extend(picks)
    note = (
        "These options are nutritionally defensible and broadly appealing but "
        "culturally generic — they don't reflect this person's actual taste. "
        "Compare with the Qloo-grounded column, which matches recommendations to "
        "a real cultural identity built from a 250M+ entity taste graph."
    )
    generic.append("")
    generic.append(note)
    return "\n".join(generic)


def _domain_for_message(message: str) -> str | None:
    """Pick the PRIMARY Qloo target domain from the message wording.

    Kept for callers that need a single value (Qloo-only composer / baseline).
    The full recommendation path uses `_domains_for_message` so combined
    "eat + wear" requests are never truncated to dining alone.
    """
    domains = _domains_for_message(message)
    return domains[0] if domains else None


# ===== Target-domain intent parsing (Bug fix: preference vs. request) =====
# The agent must separate the user's BACKGROUND preferences (what they love) from
# the CURRENT REQUEST target (what they are asking for right now). Naive keyword
# matching ordered dining before film, so "I love Midwestern food but where
# should I watch a movie?" was routed to restaurants. We now rank two layers:
#   1) explicit GOAL phrases ("watch a movie", "where to eat") — highest priority;
#   2) passive PREFERENCE vocabulary ("love food", "folk music") — used as seeds
#      only, never as the primary target when a goal phrase is present.
# All phrases are lowercased for matching.

_TARGET_DOMAIN_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    (
        "film",
        (
            "watch a movie", "watch a film", "watch movies", "watch films",
            "see a movie", "see a film", "go to the movies", "go to the cinema",
            "go to a cinema", "movie theater", "movie theatre", "cinema",
            "what to watch", "where to watch", "recommend a movie", "recommend a film",
            "a movie to watch", "films to watch", "movies to watch", "movie to watch",
        ),
    ),
    (
        "dining",
        (
            "where to eat", "what to eat", "where should i eat", "where can i eat",
            "recommend a restaurant", "recommend a dinner", "find a restaurant",
            "place to eat", "go out to eat", "eat dinner", "eat lunch", "eat breakfast",
            "what's for dinner", "whats for dinner", "dinner tonight",
        ),
    ),
    (
        "music",
        (
            "listen to music", "listen to a song", "listen to an album", "listen to a band",
            "listen to some music", "listen to a record", "recommend music",
            "recommend a song", "recommend an album", "recommend a band",
            "go to a concert", "what should i listen to", "what music should i listen",
            "what to listen to", "a band to listen",
        ),
    ),
    (
        "podcast",
        (
            "listen to a podcast", "recommend a podcast", "find a podcast",
            "a good podcast", "podcast to listen", "podcast about",
        ),
    ),
    (
        "book",
        (
            "recommend a book", "read a book", "what should i read", "what to read",
            "a book to read", "find a book", "good book to read", "a novel",
        ),
    ),
    (
        "travel",
        (
            "where should i go on vacation", "where should i go for vacation",
            "where should i go for a trip", "where should i go on a trip",
            "where should i travel", "where to go", "travel to",
            "trip to", "take a trip", "go on a trip", "go for a trip",
            "vacation", "holiday", "visit ", "destination", "go travelling",
            "place can i go", "places can i go", "which place can i go",
            "which place should i go", "a place to go", "places to go",
        ),
    ),
    (
        "fashion",
        (
            "what to wear", "what should i wear", "recommend an outfit",
            "recommend a dress", "outfit for", "dress for", "recommend clothes",
        ),
    ),
]

_PREFERENCE_DOMAIN_WORDS: dict[str, tuple[str, ...]] = {
    "dining": ("food", "cuisine", "dish", "dishes", "meal", "meals", "eat", "eating", "restaurant", "dining"),
    "film": ("movie", "movies", "film", "films", "cinema", "hollywood"),
    "music": ("music", "song", "songs", "band", "artist", "album", "folk", "jazz", "blues", "classical", "listen"),
    "podcast": ("podcast", "podcasts"),
    "book": ("book", "books", "novel", "novels", "read", "reading", "author"),
    "travel": ("travel", "trip", "vacation", "holiday", "visit", "destination", "beach", "adventure"),
    "fashion": ("fashion", "style", "clothing", "outfit", "outfits", "wear", "wearing", "dress"),
}


def _domains_for_message(message: str) -> list[str]:
    """Detect ALL Qloo target domains hinted by the message wording.

    Two layers, priority-ordered:
      1. GOAL phrases — explicit request targets ("watch a movie", "where to
         eat"). A goal phrase wins over any preference vocabulary, so
         "I love Midwestern food but where should I watch a movie?" routes to
         film first and dining only as a secondary seed domain.
      2. PREFERENCE vocabulary — passive taste background ("love food", "folk
         music"). These are appended as seed domains (never promoted above a
         goal phrase) and, when no goal phrase exists, become the fallback
         multi-domain list (so combined "eat + wear" requests still surface
         both dining and fashion as before).

    `_domain_for_message` returns the first entry, i.e. the primary target.
    """
    text = message.lower()

    # Layer 1: goal phrases, ordered by where they appear in the message.
    found: list[tuple[int, str]] = []
    for dom, phrases in _TARGET_DOMAIN_PATTERNS:
        for phrase in phrases:
            idx = text.find(phrase)
            if idx >= 0:
                found.append((idx, dom))
                break
    found.sort(key=lambda x: x[0])
    target_domains = [dom for _, dom in found]

    # Layer 2: passive preference vocabulary (seed signals, not targets).
    pref_domains = [
        dom for dom, words in _PREFERENCE_DOMAIN_WORDS.items() if any(w in text for w in words)
    ]

    # Goal domains first; preference domains appended and deduped.
    return target_domains + [d for d in pref_domains if d not in target_domains]


# Location extraction for filter.location.query — the shared recommendation path
# used to silently drop "in New York", so every returned venue came from whatever
# region Qloo happened to rank first (e.g. all-Chicago lists for a NYC request).
_KNOWN_CITIES: dict[str, str] = {
    "new york": "New York",
    "nyc": "New York",
    "manhattan": "New York",
    "boston": "Boston",
    "chicago": "Chicago",
    "los angeles": "Los Angeles",
    "la": "Los Angeles",
    "san francisco": "San Francisco",
    "sf": "San Francisco",
    "seattle": "Seattle",
    "miami": "Miami",
    "austin": "Austin",
    "atlanta": "Atlanta",
    "philadelphia": "Philadelphia",
    "washington": "Washington DC",
    "dc": "Washington DC",
    "london": "London",
    "paris": "Paris",
    "berlin": "Berlin",
    "toronto": "Toronto",
    "tokyo": "Tokyo",
    "shanghai": "Shanghai",
    "beijing": "Beijing",
    "hong kong": "Hong Kong",
    "singapore": "Singapore",
    "sydney": "Sydney",
}
_LOCATION_PROXIMITY = re.compile(
    r"\b(?:in|near|around|from|at|based in|visiting)\s+([A-Za-z][\w.'-]*(?:\s+[A-Za-z][\w.'-]*){0,3})",
)


def _extract_location(message: str) -> str | None:
    """Extract a geographic signal ("in New York", "near Boston") from free text.

    Curated alias list first (deterministic demo cities + a few Chinese city
    names), then a proper-noun fallback capped at 4 words. Returns None when the
    message has no location so callers skip filter.location.query entirely —
    the key defect was "I'm in NYC" being dropped, so recommendations ignored
    the user's actual city.
    """
    if not message:
        return None
    text = message.lower()
    for alias, canonical in _KNOWN_CITIES.items():
        if re.search(rf"\b(?:in|near|around|from|at|based in|visiting)\s+{re.escape(alias)}\b", text):
            return canonical
        if re.search(rf"\b(?:i'?m|i am)\s+(?:in|from|near)\s+{re.escape(alias)}\b", text):
            return canonical
    # 中文常见城市（demo 输入以英文为主，中文仅覆盖常用市名）
    for cn_alias, canonical in (("纽约", "New York"), ("波士顿", "Boston"), ("芝加哥", "Chicago"), ("旧金山", "San Francisco"), ("上海", "Shanghai")):
        if cn_alias in text:
            return canonical
    m = _LOCATION_PROXIMITY.search(message)
    if m:
        cand = m.group(1).strip()
        cand = re.sub(r"[\.,!?].*$", "", cand)
        cand = re.sub(
            r"\s+(?:and|but|where|what|tonight|tomorrow|today|this|for|to|would|can|should|with|while|if|that)$",
            "",
            cand,
        )
        if cand and len(cand.split()) <= 4 and cand[0].isupper():
            return cand
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
    # Persona binding (Phase 4): the web app's global persona (Maria or a custom
    # person) is sent along so the agent's cultural seeds include the persona's
    # own anchors — otherwise the "🔗 Bound to Maria" badge in AgentTab is a lie
    # and the agent only ever anchors on whatever the current message mentions.
    persona_name: str | None = Field(default=None, description="Display name of the active persona (e.g. 'Maria').")
    persona_anchors: str = Field(default="", description="Comma-separated taste anchors of the active persona, e.g. 'Frank Sinatra, Jazz, Italian cuisine'.")
    # Pure profile-lock mode (终版契约④): when 'locked' the agent grounds ONLY on
    # the persona's own anchors (+ accumulated 👍 feedback) and skips BOTH the
    # fixed core anchors and message-derived taste extraction — the reply is a
    # pure reading of the selected person's saved profile, so the Grounding panel
    # never shows off-profile seeds like "mid-century modern design" when the
    # current persona never mentioned them. 'mixed' keeps the current behaviour.
    persona_mode: str = Field(default="mixed", description="'locked' = persona anchors only; 'mixed' = persona + core + message likes.")


class ChatResponse(BaseModel):
    reply: str
    taste_entities: list[str] = Field(default_factory=list)
    taste_data_source: str = ""
    qloo_context: Any | None = None
    # Structured grounding payload for the web Grounding panel: resolved anchor
    # entities and taste-graph recommendations (with image URLs when Qloo has
    # them) plus the extracted location, so the UI shows real evidence instead
    # of a bare text block.
    taste_entity_details: list[dict[str, Any]] = Field(default_factory=list)
    taste_recommendations: list[dict[str, Any]] = Field(default_factory=list)
    taste_location: str | None = Field(default=None)


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

    # Persona-binding state annotation written into the system prompt so the
    # agent's OUTPUT contract matches the grounding state: a bound persona is
    # the ONLY taste source (its 习惯爱好 captured at profile creation — never
    # re-ask the user for their own); with no bound persona the agent asks the
    # user for their 习惯爱好 (likes/habits) AND 需求 (need) before recommending.
    system_prompt += _persona_binding_note(
        bound=bool((payload.persona_name or "").strip() or (payload.persona_anchors or "").strip()),
        persona_name=payload.persona_name,
        persona_anchors=payload.persona_anchors,
    )

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
                # Persona-first seeds: the active persona's taste anchors (sent by
                # the web app so the "🔗 Bound to Maria" badge is real) are merged
                # AHEAD of message-derived likes. This makes the Qloo-only composer
                # genuinely anchored on the current persona even when the message
                # itself only carries a domain request like "which fashionable
                # place can i go to" (no explicit cultural anchor in the text).
                # In persona_mode='locked' the message-derived likes are skipped
                # entirely: the composer grounds ONLY on the persona's saved
                # anchors, so a "where should I eat in New York" question never
                # invents new cultural entities off the question text.
                persona_likes = _persona_anchor_likes(payload.persona_anchors)
                locked = payload.persona_mode == "locked"
                message_likes = [] if locked else _extract_cultural_likes(payload.message)
                combined_likes: list[str] = []
                for like in [*persona_likes, *message_likes]:
                    if like.lower() not in [x.lower() for x in combined_likes]:
                        combined_likes.append(like)
                if combined_likes:
                    hits = await _collect_grounded_entities(client, combined_likes, max_entities=4)
                    if hits:
                        recs: list[dict[str, Any]] = []
                        target_domains = _domains_for_message(payload.message)
                        location = _extract_location(payload.message) or ""
                        try:
                            # Only forward location_query when present so fixed-signature
                            # test fakes never receive an unexpected kwarg.
                            rec_kwargs: dict[str, Any] = {}
                            if location:
                                rec_kwargs["location_query"] = location
                            ids = [h.get("id") or h.get("entity_id", "") for h in hits if h.get("id") or h.get("entity_id")]
                            rec_result = await asyncio.wait_for(
                                get_taste_based_recommendations(
                                    client,
                                    ids,
                                    target_domain=target_domains[0] if target_domains else None,
                                    limit=6,
                                    store=store,
                                    **rec_kwargs,
                                ),
                                timeout=20,
                            )
                            recs = rec_result.get("recommendations", []) or []
                            # Geographic consistency: never present a dining venue
                            # outside the requested city as grounded evidence. 位置错配
                            # 就报错 — the user sees the honest mismatch status instead
                            # of a Chicago list for a New York request.
                            if location and "dining" in target_domains[:2]:
                                recs, location_mismatches = _verify_dining_location(recs, location)
                            else:
                                location_mismatches = []
                            # Combined eat+wear requests: also fetch the secondary
                            # target domain(s) so the no-LLM composer answers BOTH
                            # "where to eat" and "what to wear".
                            for dom in target_domains[1:]:
                                extra_rec = await get_taste_based_recommendations(
                                    client,
                                    ids,
                                    target_domain=dom,
                                    limit=3,
                                    store=store,
                                    **rec_kwargs,
                                )
                                recs.extend(extra_rec.get("recommendations", []) or [])
                        except Exception:
                            recs = []
                            location_mismatches = []
                        reply = _format_qloo_only_reply(
                            hits, recs, payload.message,
                            target_domain=target_domains[0] if target_domains else None,
                            persona_name=payload.persona_name,
                        )
                        if location_mismatches:
                            reply += (
                                "\n\n🚦 Location check: Qloo returned dining venues that "
                                f"could not be verified in or near {location}. "
                                "They are reported here, not silently substituted — "
                                "please confirm the exact venue before relying on it."
                            )
                        # Dedupe taste entity names AND details. Profile likes leaking
                        # into grounding (via stored 👍 feedback) can produce the same
                        # entity twice; the web UI keys chips/recommendations off these
                        # and React 19 hard-crashes on duplicate list keys.
                        seen_taste = set()
                        unique_hits = []
                        for h in hits:
                            key = (h.get("name", "") or "").strip().lower()
                            if key and key not in seen_taste:
                                seen_taste.add(key)
                                unique_hits.append(h)
                        taste_entities = [h.get("name", "") for h in unique_hits if h.get("name")]
                        taste_context = _format_grounding_context(unique_hits)
                        return ChatResponse(
                            reply=reply,
                            taste_entities=taste_entities,
                            taste_data_source="live",
                            qloo_context=taste_context,
                            taste_entity_details=unique_hits,
                            taste_recommendations=recs,
                            taste_location=location or None,
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

    # ---- User taste profile (historical 👍 feedback) — shared by with/without Qloo branches ----
    # Read once, used twice, so both ablation arms get the exact same profile.
    try:
        profile_likes = [n for n in store.get_liked_taste_names() if n][:3]
    except Exception:
        profile_likes = []
    # Persona binding: the active persona's taste anchors (sent by the web app)
    # are merged AHEAD of profile/message likes so every recommendation is
    # grounded on the current persona — not just incidental words in the query.
    # In persona_mode='locked' the message-derived likes are skipped entirely:
    # the profile-lock mode grounds ONLY on the persona's saved anchors (+ the
    # accumulated 👍 feedback), never on new cultural entities picked from the
    # question text.
    persona_likes = _persona_anchor_likes(payload.persona_anchors)
    locked = payload.persona_mode == "locked"
    all_likes: list[str] = []
    message_likes = [] if locked else _extract_cultural_likes(payload.message)
    for like in [*persona_likes, *profile_likes, *message_likes]:
        if like.lower() not in [x.lower() for x in all_likes]:
            all_likes.append(like)

    # ---- Ablation control arm: disable_qloo=true ----
    # Single-variable principle: reuse the same CULTURAL_RECOMMENDATION_SYSTEM_PROMPT,
    # the same user taste profile, and the same temperature/task_type as the normal
    # branch. The only difference is that the Qloo entity-context block is NOT parsed
    # or injected — the isolated variable is the Qloo cultural taste graph itself.
    if payload.disable_qloo:
        ab_user = _inject_profile_likes(user_prompt, all_likes[:6])
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
    taste_entity_details: list[dict[str, Any]] = []
    taste_recommendations: list[dict[str, Any]] = []
    taste_location = _extract_location(payload.message) or None
    # Hoisted so the final LLM-failure fallback can reference the message's
    # candidate anchors even when the first try block never reached the
    # dedupe step (e.g. graph import failure) — never a bare 500.
    deduped_likes: list[str] = []
    try:
        from app.services.graph.nodes import qloo_cultural_recommend_node

        # Taste-profile evolution (Phase 2C): anchors accumulated from prior 👍
        # feedback are injected as extra cultural signals, so the agent's next
        # recommendation is grounded on the user's evolving taste — not just the
        # current message.
        # persona_mode='locked': message_likes is already [] (skipped above) and
        # the fixed core anchors are dropped too, so the seed list is a PURE read
        # of the persona's saved anchors + accumulated 👍 feedback — no invented
        # entities, ever.
        # Persona-first priority rule (终版契约④): the bound persona's own taste
        # anchors (+ accumulated feedback) are FIRST-CLASS seeds and always lead;
        # message-derived likes only supplement; the fixed core anchors (Chicago
        # blues / MCM design / craft jazz vinyl) are a LAST-RESORT fallback that
        # must never shadow a bound persona's profile — so "which place should I
        # travel" never answers with the generic three. The variable name stays
        # `deduped_likes` for the LLM-failure fallback below.
        deduped_likes = _priority_order_seeds(
            [*persona_likes, *profile_likes],
            message_likes,
            [] if locked else list(_QLOO_CORE_ANCHORS),
            _QLOO_EXCLUDE_SEEDS,
            _QLOO_EXCLUDE_KEYWORDS,
        )
        node_state: dict[str, Any] = {
            "raw_query": payload.message,
            "session_id": payload.session_id,
            "feedback_store": store,
            "entities": {
                "cultural_likes": deduped_likes,
                "target_domain": _domain_for_message(payload.message) or "",
                "target_domains": _domains_for_message(payload.message),
                "location_query": _extract_location(payload.message) or "",
                # persona_mode 透传给 Qloo Agent 图：locked 时 build_qloo_query
                # 不得从问句提取 message likes（档案锚点 PURE read），route_intent
                # 也据此用锚点兜底进入 Qloo 节点而非误报"实体无法映射"。
                "persona_mode": payload.persona_mode,
                # Structured-template excludes: seed-level blacklist + result-side
                # class keywords, consumed by qloo_cultural_recommend_node.
                "exclude_seeds": list(_QLOO_EXCLUDE_SEEDS),
                "exclude_keywords": list(_QLOO_EXCLUDE_KEYWORDS),
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
            # B-arm qloo agent StateGraph (input_node -> intent_node -> build_qloo_query
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
            # Single-variable parity with the disable_qloo baseline: BOTH branches
            # carry the same accumulated taste-profile likes so the LLM narration
            # is grounded on the user's full persona, not just this message.
            user_prompt = _inject_profile_likes(user_prompt, all_likes[:6])
            user_prompt = f"{injected.strip()}\n\n{user_prompt}"
            taste_entities = resolved_names
            taste_data_source = "live"
            # Structured grounding payload for the web panel: resolved anchor
            # entities (with image URLs) and the taste-graph recommendations.
            details = node_result.get("taste_entities") or []
            taste_entity_details = details if isinstance(details, list) else []
            recs_out = node_result.get("qloo_recommendations") or []
            taste_recommendations = recs_out if isinstance(recs_out, list) else []
            # Geographic consistency for the LLM path too: dining venues outside
            # the requested city must never be presented as grounded evidence.
            # Mismatches are reported in the reply, not silently dropped.
            if taste_location and "dining" in (_domains_for_message(payload.message)):
                kept, mismatched = _verify_dining_location(taste_recommendations, taste_location)
                taste_recommendations = kept
                if mismatched:
                    user_prompt += (
                        "\n\n[Location check] Some Qloo dining results could not be "
                        f"verified in or near {taste_location}. Mention (briefly) that "
                        "those venues were excluded from the recommendation; do not "
                        "present a wrong-city venue as the user's local choice."
                    )
        elif node_result.get("last_error"):
            logger.warning("Qloo node degraded: %s", node_result["last_error"])
        elif node_result.get("fallback_message"):
            logger.info("Qloo agent fallback: %s", node_result["fallback_message"])
    except Exception:
        taste_entities, taste_data_source, qloo_context = [], "", None

    # Final LLM synthesis. This is intentionally the LAST line of defense: even
    # if the LangGraph run above already produced live Qloo grounding, an LLM
    # outage (rate limit / timeout / revoked key) must NEVER surface as a 500 to
    # the demo. When the LLM fails we degrade to the deterministic Qloo-only
    # composer — the reply keeps real cultural data and the grounding payload
    # (taste_entities / qloo_context) is still delivered to the frontend.
    try:
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
    except Exception:
        logger.warning(
            "LLM synthesis failed after Qloo grounding — degrading to deterministic Qloo-only reply",
            exc_info=True,
        )
        # Real Qloo data (resolved anchors + taste recommendations) is available;
        # answer from the taste graph instead of an apology. When the details
        # payload exists use it (richer rendering: domain/score/image); otherwise
        # rebuild name-only hits from the resolved names.
        if taste_entity_details:
            hits = list(taste_entity_details)
        else:
            hits = [
                {
                    "name": n,
                    "type": "taste-entity",
                    "domain": _domain_for_message(payload.message) or "mixed",
                }
                for n in taste_entities
            ]
        if hits or taste_recommendations or qloo_context:
            reply = _format_qloo_only_reply(
                hits,
                taste_recommendations or [],
                payload.message,
                target_domain=_domain_for_message(payload.message) or None,
            )
            taste_data_source = "live"
        elif locked:
            # persona_mode='locked': the seed list is a PURE read of the persona's
            # saved anchors — telling the user to "try a more specific name" is
            # nonsense here, because locked mode deliberately refuses to invent
            # new entities from the question text. Never emit the generic
            # "didn't map to anything in Qloo's taste graph" fallback in locked
            # mode; instead own the lock honestly and point at the exits
            # (unlock the profile, or explore in the Tastes / Senior Dining tabs).
            anchor_txt = ", ".join(persona_likes[:2]) if persona_likes else "your persona's saved taste anchors"
            reply = (
                "Your profile is locked to your persona's saved taste anchors "
                f"({anchor_txt}), but Qloo returned no grounded match for this "
                "request, so I won't invent a cultural link that isn't there. "
                "Try a different ask, switch the profile lock OFF so I can also "
                "explore new tastes from your question, or head to the Tastes / "
                "Senior Dining tabs for live grounding."
            )
            taste_data_source = "preview"
        else:
            # No anchor could be resolved at any retry depth. Never surface a raw
            # "LLM down / no grounding" error to the demo — give a review-friendly
            # guidance instead (user decision: option 1 retry first, option 2 text
            # as the LAST fallback). The listed names are the user-facing seeds:
            # message likes first, then persona anchors — NEVER the fixed core
            # anchors (those would surface "classic Chicago blues didn't map" for
            # a message that never mentioned Chicago blues).
            fallback_likes = message_likes or persona_likes or deduped_likes
            anchor_txt = ", ".join(fallback_likes[:2]) if fallback_likes else "that phrase"
            reply = (
                "I couldn't resolve a cultural anchor from your request — "
                f"{anchor_txt} didn't map to anything in Qloo's taste graph "
                "(maybe too generic, or the entity type isn't indexed yet). "
                "Try a specific well-known name such as『Federico Fellini』, "
                "『Chicago blues』or『jazz』, and I'll ground real recommendations on it. "
                "The Senior Dining / TasteBridge tabs also stay available."
            )
            taste_data_source = "preview"
    return ChatResponse(
        reply=reply,
        taste_entities=taste_entities,
        taste_data_source=taste_data_source,
        qloo_context=qloo_context,
        taste_entity_details=taste_entity_details,
        taste_recommendations=taste_recommendations,
        taste_location=taste_location,
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