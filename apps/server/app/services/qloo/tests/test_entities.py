"""`entities._normalize` must handle BOTH Qloo response shapes:

- /v2/insights entities carry `subtype` (e.g. `urn:entity:movie`).
- /search entities carry ONLY `types: ["urn:entity:movie"]` — no `subtype`.

The /search shape used to silently blank the `domain` (the bug fixed by
`_resolve_subtype`); these tests pin the two-shape contract.
"""
from __future__ import annotations

from app.services.qloo.entities import _normalize, _resolve_subtype


def test_resolve_subtype_from_types_only_search_entity():
    raw = {"name": "My Neighbor Totoro", "entity_id": "abc-123", "types": ["urn:entity:movie"]}
    assert _resolve_subtype(raw) == "urn:entity:movie"


def test_resolve_subtype_prefers_explicit_subtype():
    raw = {"name": "Muse", "entity_id": "e1", "subtype": "urn:entity:artist", "types": ["urn:entity:movie"]}
    assert _resolve_subtype(raw) == "urn:entity:artist"


def test_normalize_search_entity_types_only_maps_domain():
    raw = {
        "name": "Murder on the Orient Express",
        "entity_id": "abc-456",
        "types": ["urn:entity:book"],
    }
    norm = _normalize(raw)
    assert norm["entity_id"] == "abc-456"
    assert norm["type"] == "urn:entity:book"
    assert norm["domain"] == "book"


def test_normalize_insights_entity_with_subtype():
    raw = {"name": "Radiohead", "entity_id": "e1", "subtype": "urn:entity:artist"}
    norm = _normalize(raw)
    assert norm["type"] == "urn:entity:artist"
    assert norm["domain"] == "music"


def test_normalize_dining_place_types_only():
    raw = {"name": "Blue Hill", "entity_id": "e2", "types": ["urn:entity:place"]}
    norm = _normalize(raw)
    assert norm["type"] == "urn:entity:place"
    assert norm["domain"] == "dining"


def test_normalize_unknown_types_falls_back_to_raw():
    raw = {"name": "Something", "entity_id": "e3", "types": ["urn:entity:unknown_thing"]}
    norm = _normalize(raw)
    assert norm["type"] == "urn:entity:unknown_thing"
    assert norm["domain"] == "urn:entity:unknown_thing"