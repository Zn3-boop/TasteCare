"""USDA-backed nutrition screening — the data layer behind TasteCare's health constraints.

Boundaries (deliberate, per product decision):

  ✅ USDA FoodData Central provides sodium / protein / fiber / calories directly.
     This module ships a small offline reference table (app/data/usda_foods.json)
     extracted from USDA FoodData Central values (per 100 g), so the demo needs
     no API key and no network at runtime.
  ⚠️  Texture ("soft chewable") is NOT a USDA field. We carry our own curated
     soft/medium/hard whitelist alongside each food row. It is a self-maintained
     supplement, not USDA data — and the code says so.
  ❌  Drug-food interactions are NOT covered by USDA (nutrition tables, not
     pharmacology). Medication screening stays in tastecare._MED_RULES as a small
     handwritten whitelist and is always labelled as a screening + disclaimer.

The matcher is deliberately conservative: it only attaches USDA numbers when a
food keyword actually matches the restaurant name/tags/description, so we never
invent nutrition facts for a venue we don't know.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_DB_PATH = _DATA_DIR / "usda_foods.json"


@lru_cache(maxsize=1)
def load_usda_db() -> dict[str, Any]:
    """Load the offline USDA reference table (cached, zero I/O on hot path)."""
    with open(_DB_PATH, encoding="utf-8") as f:
        return json.load(f)


def _food_haystack(food: dict[str, Any]) -> str:
    return " ".join([food.get("name", ""), *food.get("keywords", [])]).lower()


def match_usda_food(text: str) -> dict[str, Any] | None:
    """Return the best-matching USDA food row for arbitrary venue text, or None.

    Matching is substring-based and only fires on real keyword hits. When several
    foods match, the longest keyword wins (most specific term), which avoids e.g.
    "spaghetti" collapsing into the generic "pasta" row.
    """
    if not text:
        return None
    hay = text.lower()
    db = load_usda_db()
    best: dict[str, Any] | None = None
    best_len = 0
    for food in db.get("foods", []):
        for kw in food.get("keywords", []):
            if kw.lower() in hay and len(kw) > best_len:
                best = food
                best_len = len(kw)
    return best


def nutrition_label(row: dict[str, Any]) -> str:
    """Short human label like `USDA 1mg Na · 5.8g protein · 2.4g fiber /100g`."""
    p = row.get("per_100g", {})
    return (
        f"USDA {p.get('sodium_mg', 0):.0f}mg Na · "
        f"{p.get('protein_g', 0):.1f}g protein · "
        f"{p.get('fiber_g', 0):.1f}g fiber /100g"
    )


def sodium_check(row: dict[str, Any], threshold_mg: int | None = None) -> tuple[bool, str | None]:
    """(passes, note) for low-sodium constraint against the row's USDA value.

    Uses the table's `sodium_low_threshold_mg_per_100g` by default. Returns a
    plain-language English note the UI can show directly.
    """
    db = load_usda_db()
    threshold = threshold_mg if threshold_mg is not None else int(
        db.get("_meta", {}).get("sodium_low_threshold_mg_per_100g", 140)
    )
    sodium = row.get("per_100g", {}).get("sodium_mg", 0)
    if sodium <= threshold:
        return True, f"Low sodium ✓ (USDA {sodium:.0f}mg Na /100g, ≤ {threshold}mg)"
    return False, f"Sodium high ⚠ (USDA {sodium:.0f}mg Na /100g, > {threshold}mg)"


def texture_check(row: dict[str, Any]) -> tuple[bool, str]:
    """(passes, note) for soft-chewable constraint using our curated whitelist."""
    texture = row.get("texture", "medium")
    if texture == "soft":
        return True, "Soft texture ✓ (whitelist: soft)"
    if texture == "hard":
        return False, "Hard / hard to chew ⚠ (whitelist: hard)"
    return True, "Medium texture (whitelist: medium)"
