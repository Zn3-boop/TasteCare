from __future__ import annotations

import logging
from typing import Any

from app.services.qloo.client import QlooClient

logger = logging.getLogger(__name__)

SUPPORTED_DOMAINS = ["music", "film", "dining", "fashion", "travel", "podcast", "book"]

# friendly domain -> Qloo entity type URN (same mapping as taste.py)
_DOMAIN_TO_ETYPE: dict[str, str] = {
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

_ETYPE_TO_DOMAIN: dict[str, str] = {
    "urn:entity:artist": "music",
    "urn:entity:movie": "film",
    "urn:entity:tv_show": "tv",
    "urn:entity:place": "dining",
    "urn:entity:brand": "fashion",
    "urn:entity:destination": "travel",
    "urn:entity:podcast": "podcast",
    "urn:entity:book": "book",
}


def resolve_entity_type(domain: str | None) -> str | None:
    if not domain:
        return None
    return _DOMAIN_TO_ETYPE.get(domain.strip().lower())


def _extract_entities(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if "error" in payload:
        return []
    results = payload.get("results")
    if isinstance(results, dict):
        return results.get("entities") or []
    if isinstance(results, list):
        return results
    return []


def _resolve_subtype(raw: dict[str, Any]) -> str:
    """Qloo /search returns entities WITHOUT `subtype` — only `types: [URN]`.

    /v2/insights returns entities WITH `subtype`. Normalize both to an entity-type URN.
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


def _normalize(raw: dict[str, Any]) -> dict[str, Any]:
    entity_id = raw.get("entity_id", "")
    subtype = _resolve_subtype(raw)
    image = None
    props = raw.get("properties")
    if isinstance(props, dict):
        img = props.get("image")
        if isinstance(img, dict):
            image = img.get("url")
        elif isinstance(img, str):
            image = img
    return {
        "id": entity_id,
        "entity_id": entity_id,
        "name": raw.get("name", ""),
        "type": subtype,
        "domain": _ETYPE_TO_DOMAIN.get(subtype, subtype),
        "image": image,
        "popularity": raw.get("popularity"),
    }


async def resolve_entity(
    client: QlooClient,
    name: str,
    domain: str | None = None,
) -> dict[str, Any] | None:
    from app.services.qloo.taste import search_cultural_entities
    results = await search_cultural_entities(client, name, domain=domain, limit=1)
    if results:
        return results[0]
    return None


async def resolve_entities_batch(
    client: QlooClient,
    names: list[str],
    domain: str | None = None,
) -> list[dict[str, Any]]:
    resolved = []
    for name in names:
        entity = await resolve_entity(client, name, domain=domain)
        if entity:
            resolved.append(entity)
    return resolved


async def get_entity_details(
    client: QlooClient,
    entity_id: str,
) -> dict[str, Any]:
    # No legacy /entities/{id} endpoint; resolve via insights restricted to the
    # candidate entity so we return its details/tags alongside resulting entities.
    # NOTE: results-only (no signal) is intentional — Qloo's hackathon API returns
    # an empty set when signal_entities == results_entities (verified live).
    etype = "urn:entity:place"
    payload = await client.insights(
        filter_type=etype,
        results_entities=[entity_id],
        take=1,
    )
    if "error" in payload:
        return {"id": entity_id, "error": payload.get("error")}
    hits = _extract_entities(payload)
    if hits:
        return _normalize(hits[0])
    return {"id": entity_id, "error": "not_found"}


async def get_entity_taste_profile(
    client: QlooClient,
    entity_ids: list[str],
) -> dict[str, Any]:
    if not entity_ids:
        return {"error": "no_entities", "profile": {}}
    etype = "urn:entity:artist"
    # results-only (no signal) so Qloo returns the requested entities themselves
    # (signal_entities == results_entities returns an empty set on the hackathon API).
    payload = await client.insights(
        filter_type=etype,
        results_entities=entity_ids,
        take=len(entity_ids),
    )
    if "error" in payload:
        return {"error": payload.get("error"), "profile": {}}
    entities = [_normalize(e) for e in _extract_entities(payload)]
    return {"profile": {"entities": entities, "count": len(entities)}}


async def score_cultural_fit(
    client: QlooClient,
    seed_names: list[str],
    candidate_names: list[str],
    domain: str | None = None,
) -> dict[str, Any]:
    from app.services.qloo.taste import search_cultural_entities
    seed_ids = []
    for name in seed_names:
        results = await search_cultural_entities(client, name, domain=domain, limit=1)
        if results:
            eid = results[0].get("entity_id", "")
            if eid:
                seed_ids.append(eid)
    candidate_ids = []
    candidate_map: dict[str, str] = {}
    for name in candidate_names:
        results = await search_cultural_entities(client, name, domain=domain, limit=1)
        if results:
            eid = results[0].get("entity_id", "")
            if eid:
                candidate_ids.append(eid)
                candidate_map[eid] = name
    if not seed_ids or not candidate_ids:
        return {"scores": [], "error": "could_not_resolve_entities"}

    etype = resolve_entity_type(domain) or "urn:entity:artist"
    payload = await client.insights(
        filter_type=etype,
        signal_entities=seed_ids,
        results_entities=candidate_ids,
        take=len(candidate_ids),
    )
    if "error" in payload:
        return {"scores": [], "error": payload.get("error")}

    matched = _extract_entities(payload)
    enriched = []
    for idx, e in enumerate(matched):
        eid = e.get("entity_id", "")
        enriched.append({
            "entity_id": eid,
            "name": candidate_map.get(eid, e.get("name", "Unknown")),
            "rank": idx,
            "score": _affinity_score(e, idx, len(matched)),
            "domain": domain or "",
        })
    enriched.sort(key=lambda x: x["score"], reverse=True)
    return {"scores": enriched}


def _affinity_score(entity: dict[str, Any], rank: int, total: int) -> float:
    """Best-effort affinity estimate from returned order + popularity signal.

    Qloo sorts results by affinity; we surface a normalized estimate rather than
    pretending the API returns an explicit 0-1 match percentage.
    """
    popularity = entity.get("popularity")
    if isinstance(popularity, (int, float)):
        return float(popularity)
    if total > 1:
        return max(0.0, 1.0 - (rank / (total - 1)) * 0.5)
    return 0.5