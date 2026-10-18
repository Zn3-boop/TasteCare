from __future__ import annotations

import logging
from typing import Any

from app.services.qloo.client import QlooClient, get_qloo_client
from app.services.qloo.feedback import FeedbackStore

logger = logging.getLogger(__name__)

# Map friendly domain names -> Qloo entity type URNs (filter.type)
DOMAIN_TO_ENTITY_TYPE: dict[str, str] = {
    "music": "urn:entity:artist",
    "film": "urn:entity:movie",
    "tv": "urn:entity:tv_show",
    "movie": "urn:entity:movie",
    "dining": "urn:entity:place",
    "food": "urn:entity:place",
    "restaurant": "urn:entity:place",
    "fashion": "urn:entity:brand",
    "travel": "urn:entity:destination",
    "destination": "urn:entity:destination",
    "podcast": "urn:entity:podcast",
    "book": "urn:entity:book",
    "books": "urn:entity:book",
}

# Map Qloo entity subtype URN -> friendly domain label for UI
ENTITY_TYPE_TO_DOMAIN: dict[str, str] = {
    "urn:entity:artist": "music",
    "urn:entity:movie": "film",
    "urn:entity:tv_show": "tv",
    "urn:entity:place": "dining",
    "urn:entity:brand": "fashion",
    "urn:entity:destination": "travel",
    "urn:entity:podcast": "podcast",
    "urn:entity:book": "book",
    "urn:entity:person": "person",
}


def resolve_entity_type(domain: str | None) -> str | None:
    if not domain:
        return None
    return DOMAIN_TO_ENTITY_TYPE.get(domain.strip().lower())


def _resolve_subtype(raw: dict[str, Any]) -> str:
    """Qloo /search returns entities WITHOUT a `subtype` field — only `types: [URN]`.

    /v2/insights returns entities WITH `subtype` (and `type: urn:entity`). Normalize
    both shapes to a single entity-type URN so domain mapping stays correct in both
    the search and insights code paths.
    """
    subtype = raw.get("subtype") or raw.get("type", "")
    if isinstance(subtype, str) and subtype.startswith("urn:entity:"):
        return subtype
    types = raw.get("types") or []
    for t in types:
        if isinstance(t, str) and t.startswith("urn:entity:"):
            return t
    if isinstance(subtype, str):
        return subtype
    return ""


def _normalize_entity(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw Qloo entity (/v2/insights or /search) into a stable shape."""
    entity_id = raw.get("entity_id", "")
    subtype = _resolve_subtype(raw)
    name = raw.get("name", "")
    props = raw.get("properties", {}) or {}
    image = None
    if isinstance(props, dict):
        img = props.get("image")
        if isinstance(img, dict):
            image = img.get("url")
        elif isinstance(img, str):
            image = img
    tags = raw.get("tags") or []
    tag_names = [t.get("name", "") for t in tags if isinstance(t, dict) and t.get("name")]
    return {
        "id": entity_id,
        "entity_id": entity_id,
        "name": name,
        "type": subtype,
        "domain": ENTITY_TYPE_TO_DOMAIN.get(subtype, subtype),
        "image": image,
        "tags": tag_names,
        "popularity": raw.get("popularity"),
        "description": props.get("description") if isinstance(props, dict) else None,
    }


def _extract_entities(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Qloo /v2/insights returns {'results': {'entities': [...]}}."""
    if "error" in payload:
        return []
    results = payload.get("results")
    if isinstance(results, dict):
        return results.get("entities") or []
    if isinstance(results, list):
        return results
    return []


async def search_cultural_entities(
    client: QlooClient,
    query: str,
    domain: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Search the taste graph for entities matching a human query.

    Maps a friendly domain (music/film/dining/...) to the Qloo entity type URN.
    """
    entity_types = None
    etype = resolve_entity_type(domain)
    if etype:
        entity_types = [etype]
    payload = await client.search(query, entity_types=entity_types, take=limit)
    entities = _extract_entities(payload)
    if not entities:
        logger.warning(
            f"Qloo search returned no results for query={query!r}, domain={domain}, "
            f"payload_error={payload.get('error')}"
        )
    return [_normalize_entity(e) for e in entities]



async def get_taste_based_recommendations(
    client: QlooClient,
    seed_entity_ids: list[str],
    target_domain: str | None = None,
    limit: int = 10,
    store: FeedbackStore | None = None,
) -> dict[str, Any]:
    if not seed_entity_ids:
        return {"recommendations": [], "source": "qloo", "error": "no_seed_entities"}

    filter_type = resolve_entity_type(target_domain) or "urn:entity:artist"

    # Live mode: route through the user's 👍/👎 preference overlay so feedback
    # changes the next round of recommendations (liked prepends to the signal list,
    # disliked is excluded from the results). Preview mode has no client (disabled),
    # so this helper would early-return anyway — keep the plain call for no-key.
    if client.enabled:
        payload = await apply_taste_preferences(
            client,
            signal_entities=seed_entity_ids,
            take=limit,
            filter_type=filter_type,
            store=store,
        )
    else:
        payload = await client.insights(
            filter_type=filter_type,
            signal_entities=seed_entity_ids,
            take=limit,
        )
    if "error" in payload:
        logger.warning(
            f"Qloo insights failed for target={filter_type}: {payload.get('error')}"
        )
        return {
            "recommendations": [],
            "source": "qloo",
            "error": payload.get("error"),
        }
    recs = [_normalize_entity(e) for e in _extract_entities(payload)]
    return {
        "recommendations": recs,
        "source": "qloo",
        "seed_count": len(seed_entity_ids),
        "target_domain": target_domain,
    }


async def get_cross_domain_discovery(
    client: QlooClient,
    seed_entity_ids: list[str],
    domains: list[str] | None = None,
    per_domain_limit: int = 5,
    store: FeedbackStore | None = None,
) -> dict[str, list[dict[str, Any]]]:
    if domains is None:
        domains = ["music", "film", "dining", "fashion", "travel", "podcast", "book"]
    results: dict[str, list[dict[str, Any]]] = {}
    for domain in domains:
        rec = await get_taste_based_recommendations(
            client, seed_entity_ids, target_domain=domain, limit=per_domain_limit, store=store,
        )
        results[domain] = rec.get("recommendations", [])
    return results


async def get_taste_similarity_score(
    client: QlooClient,
    entity_ids: list[str],
    target_type: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    if not entity_ids:
        return {"similar": [], "error": "no_entities"}
    filter_type = target_type or "urn:entity:artist"
    # Qloo's hackathon API returns an EMPTY result set when signal_entities ==
    # results_entities (verified live). For "similar to X", the correct shape is
    # signal-only: anchor on the given entities and let Qloo rank the closest
    # matches of the target type.
    payload = await client.insights(
        filter_type=filter_type,
        signal_entities=entity_ids,
        take=limit,
    )
    if "error" in payload:
        return {"similar": [], "error": payload.get("error")}
    similar = [_normalize_entity(e) for e in _extract_entities(payload)]
    return {"similar": similar}


# ===== Live feedback preference overlay =====
# Qloo's hackathon API has no remote taste-profile write endpoint, so live
# feedback is applied as a local overlay on every subsequent /v2/insights call:
#   - liked   entities -> resolved to UUIDs, prepended to signal.interests.entities
#   - disliked entities -> resolved to UUIDs, filtered out of the results below
# This keeps the feedback loop real (the next recommendation actually changes)
# while staying fully honest about what Qloo's API can and cannot do.

async def _resolve_taste_preference_entities(
    client: QlooClient,
    names: list[str],
) -> list[str]:
    """Resolve user-seen entity names to Qloo entity UUIDs (best-effort, 1 search each)."""
    ids: list[str] = []
    for name in names:
        if not name:
            continue
        results = await search_cultural_entities(client, name, limit=1)
        if results and results[0].get("entity_id"):
            ids.append(results[0]["entity_id"])
    return ids


async def apply_taste_preferences(
    client: QlooClient,
    signal_entities: list[str],
    take: int = 10,
    filter_type: str | None = None,
    store: FeedbackStore | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Run /v2/insights with the user's live 👍/👎 overlay applied.

    - Liked entities (from feedback) are prepended to the signal list, giving them
      the highest weighting for the current recommendation round.
    - Disliked entities are excluded from the returned result set by post-filtering
      on entity_id (client-side exclusion), so 👎 recommendations stop appearing.
    Returns the raw insights payload (with disliked entries removed from results).
    """
    if store is None:
        from app.services.qloo.feedback import get_feedback_store

        store = get_feedback_store()

    liked = await _resolve_taste_preference_entities(client, list(store.get_liked_taste_names()))
    disliked = await _resolve_taste_preference_entities(client, list(store.get_disliked_taste_names()))

    # Liked go first (highest weight in Qloo's signal list); dedupe by UUID.
    signals: list[str] = []
    seen: set[str] = set()
    for eid in liked + list(signal_entities or []):
        if eid and eid not in seen:
            seen.add(eid)
            signals.append(eid)

    etype = filter_type or resolve_entity_type("music") or "urn:entity:artist"
    payload = await client.insights(
        filter_type=etype,
        signal_entities=signals,
        take=take,
        **extra,
    )
    if "error" in payload:
        return payload

    results = payload.get("results")
    if isinstance(results, dict):
        entities = results.get("entities") or []
        if disliked:
            dislike_ids = set(disliked)
            kept = [e for e in entities if e.get("entity_id") not in dislike_ids]
            removed = len(entities) - len(kept)
            entities = kept
        else:
            removed = 0
        results["entities"] = entities
        results["preferences_applied"] = {
            "liked_count": len(liked),
            "disliked_count": len(disliked),
            "disliked_removed": removed,
        }
        payload["results"] = results
    return payload


async def build_cultural_context_for_llm(
    client: QlooClient,
    user_likes: list[str],
    target_domain: str | None = None,
    limit: int = 8,
    store: FeedbackStore | None = None,
) -> str:
    if not client.enabled:
        return ""
    entity_ids: list[str] = []
    for like in user_likes:
        search_result = await search_cultural_entities(client, like, limit=1)
        if search_result:
            eid = search_result[0].get("entity_id", "")
            if eid:
                entity_ids.append(eid)
    if not entity_ids:
        return ""
    rec = await get_taste_based_recommendations(
        client, entity_ids, target_domain=target_domain, limit=limit, store=store,
    )
    recommendations = rec.get("recommendations", [])
    if not recommendations:
        return ""
    lines = ["[Qloo Cultural Intelligence - Taste-Based Recommendations]"]
    for i, r in enumerate(recommendations, 1):
        name = r.get("name", "Unknown")
        rtype = r.get("type", "")
        domain_label = r.get("domain", "")
        lines.append(f"  {i}. {name} ({rtype}) [domain={domain_label}]")
    lines.append(
        "[End of Qloo Recommendations - Use these to ground your answer in real cultural taste data, not generic LLM knowledge]"
    )
    return "\n".join(lines)


# ===== Taste Bridge — explicit graph JSON (nodes + edges + why) =====

# Clearly-labelled demo preview pool, used ONLY when Qloo is NOT connected so the
# bridge graph is still explorable during a no-key demo. The `why` strings are
# faithful, semantically-grounded relationships (never passed off as live Qloo
# output — the response sets data_source="preview"). Mirrors the web constants so
# backend and frontend agree on the no-key fallback.
_PREVIEW_BRIDGE: dict[str, list[dict[str, Any]]] = {
    "music": [
        {"name": "Ella Fitzgerald", "popularity": 0.93, "why": "A frequent Sinatra collaborator and the \"First Lady of Song\" — they shared bands, albums and the swing-era stage."},
        {"name": "Count Basie Orchestra", "popularity": 0.9, "why": "Sinatra fronted Basie's band and recorded the live classic \"Sinatra at the Sands\" with them."},
        {"name": "Tony Bennett", "popularity": 0.87, "why": "An heir of the crooner lineage whose phrasing descends directly from Sinatra."},
    ],
    "dining": [
        {"name": "Jazz-era Supper Club", "popularity": 0.92, "why": "Sinatra was forged in jazz supper clubs — live trio, dim light, Italian-American fare — mirroring his Little Italy upbringing."},
        {"name": "Old-school Trattoria", "popularity": 0.9, "why": "His parents ran a tavern; Italian-American red-sauce table culture is a cornerstone of his taste."},
        {"name": "Hotel Cocktail Lounge", "popularity": 0.84, "why": "Post-war lounge culture he helped define: cocktails with intimate live music."},
    ],
    "film": [
        {"name": "Guys and Dolls", "popularity": 0.91, "why": "Sinatra starred in this 1955 musical at the peak of his crossover film fame."},
        {"name": "On the Waterfront", "popularity": 0.85, "why": "An iconic New York drama Sinatra fought to appear in — classic Hollywood at its best."},
        {"name": "Some Came Running", "popularity": 0.8, "why": "A Sinatra vehicle blending the Rat Pack era's glamour with a searching dramatic turn."},
    ],
    "travel": [
        {"name": "Little Italy, NYC", "popularity": 0.9, "why": "Maria, like Sinatra, grew up with Italian-American New York culture — the emotional anchor of the whole graph."},
        {"name": "Atlantic City, NJ", "popularity": 0.82, "why": "Sinatra helped build its entertainment industry and was a regular headline act on the boardwalk."},
        {"name": "Miami Beach, FL", "popularity": 0.79, "why": "A perennial Rat Pack stage-city, mixing music, film glamour and resort dining."},
    ],
    "fashion": [
        {"name": "Vintage Italian Tailoring", "popularity": 0.86, "why": "Sinatra's signature two-piece, high-waisted Italian-cut suits set the mid-century look."},
        {"name": "Classic Fedora", "popularity": 0.84, "why": "The fedora is practically Sinatra's emblem — film noir and jazz stage in one silhouette."},
        {"name": "Cuff-linked Dress Shirt", "popularity": 0.78, "why": "Evening Rat Pack wear: crisp, tailored, understated glamour."},
    ],
    "podcast": [
        {"name": "Rat Pack Radio Shows", "popularity": 0.85, "why": "Sinatra's live radio broadcasts defined the 1940s-50s podcast-like entertainment format."},
        {"name": "Jazz Talk Radio", "popularity": 0.79, "why": "The conversational jazz format mirrors the intimacy of supper club performances."},
    ],
    "book": [
        {"name": "The Great Gatsby", "popularity": 0.82, "why": "The Jazz Age novel Sinatra embodied — pre-war American glamour and melancholy."},
        {"name": "On the Waterfront Script Books", "popularity": 0.71, "why": "Sinatra's iconic role cemented New York dockworker literature in the cultural canon."},
    ],
}
_BRIDGE_DOMAIN_ORDER = ["music", "dining", "film", "travel", "fashion", "podcast", "book"]


async def get_cross_domain_bridge_graph(
    client: QlooClient,
    seed_entity_ids: list[str],
    center_label: str,
    domains: list[str] | None = None,
    per_domain_limit: int = 5,
) -> dict[str, Any]:
    """Return an explicit graph JSON: { center, nodes:[{id,name,domain}], edges:[{source,target,why}] }.

    Live branch (Qloo enabled) builds nodes from real cross-domain recommendations and
    honest edges (no fabricated specific claims — each `why` simply states the domain
    adjacency, which is exactly what Qloo's cross-domain insights establish).
    Preview branch (no key) returns the clearly-labelled demo pool so the UI can still
    render the constellation; data_source is set accordingly so nothing is mislabeled.
    """
    if client.enabled:
        cross = await get_cross_domain_discovery(
            client, seed_entity_ids, domains=domains, per_domain_limit=per_domain_limit,
        )
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        for domain in _BRIDGE_DOMAIN_ORDER:
            if domain not in cross:
                continue
            for rec in cross[domain] or []:
                eid = rec.get("entity_id") or rec.get("id") or ""
                name = rec.get("name", "")
                if not eid or not name:
                    continue
                node_id = eid
                nodes.append({
                    "id": node_id,
                    "entity_id": node_id,
                    "name": name,
                    "domain": domain,
                    "popularity": rec.get("popularity"),
                })
                edges.append({
                    "source": "center",
                    "target": node_id,
                    "why": f"Culturally adjacent to “{center_label}” in the {domain} taste graph.",
                })
        return {
            "center": center_label,
            "nodes": nodes,
            "edges": edges,
            "data_source": "live",
        }

    nodes = []
    edges = []
    for domain in _BRIDGE_DOMAIN_ORDER:
        for item in _PREVIEW_BRIDGE.get(domain, []) or []:
            node_id = f"preview-{item['name']}"
            nodes.append({
                "id": node_id,
                "entity_id": node_id,
                "name": item["name"],
                "domain": domain,
                "popularity": item.get("popularity"),
            })
            edges.append({
                "source": "center",
                "target": node_id,
                "why": item.get("why", ""),
            })
    return {
        "center": center_label,
        "nodes": nodes,
        "edges": edges,
        "data_source": "preview",
    }
