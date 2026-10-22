"""Tests for the USDA-backed nutrition screening layer.

Verifies the boundary contract (documented in app/services/nutrition/usda.py):

  ✅ USDA FoodData Central supplies sodium / protein / fiber / calories.
     match_usda_food() maps venue text → a real offline food row with numbers.
     sodium_check() compares against the USDA sodium value with the low-sodium
     threshold from the table meta.
  ⚠️  Texture is a SELF-MAINTAINED whitelist (USDA has no texture field).
     texture_check() returns soft/medium/hard from our curated table, and the
     tastecare integration surfaces this as the soft-chewable constraint.
  ❌  Medication screening is NOT in the USDA table — it stays in tastecare's
     handwritten _MED_RULES and is never fabricated from nutrition data.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SERVER_ROOT = Path(__file__).resolve().parent.parent
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from app.services.nutrition.usda import (  # noqa: E402
    load_usda_db,
    match_usda_food,
    nutrition_label,
    sodium_check,
    texture_check,
)
from app.services.qloo.tastecare import (  # noqa: E402
    _annotate_health,
    _MED_RULES,
)


class TestUsdaDatabase:
    def test_db_loads_with_foods(self):
        db = load_usda_db()
        assert "foods" in db
        assert len(db["foods"]) >= 30
        assert db["_meta"]["source"].startswith("USDA FoodData Central")

    def test_every_food_row_schema(self):
        db = load_usda_db()
        for f in db["foods"]:
            assert f["id"].startswith("usda-")
            assert f["texture"] in {"soft", "medium", "hard"}
            p = f["per_100g"]
            for key in ("sodium_mg", "protein_g", "fiber_g", "kcal"):
                assert key in p
            assert isinstance(f["keywords"], list) and f["keywords"]

    def test_meta_thresholds(self):
        db = load_usda_db()
        assert db["_meta"]["sodium_low_threshold_mg_per_100g"] == 140

    def test_ids_unique(self):
        db = load_usda_db()
        ids = [f["id"] for f in db["foods"]]
        assert len(ids) == len(set(ids))


class TestMatchUsdaFood:
    def test_match_pasta_by_tag(self):
        assert match_usda_food("trattoria spaghetti carbonara")["id"] == "usda-pasta-cooked"

    def test_match_tofu_by_name(self):
        assert match_usda_food("Silken Tofu House")["id"] == "usda-tofu"

    def test_match_congee(self):
        assert match_usda_food("Congee House porridge")["id"] == "usda-congee"

    def test_match_salmon(self):
        assert match_usda_food("Grilled Salmon Grill")["id"] == "usda-salmon"

    def test_match_nuts_hard(self):
        assert match_usda_food("Roasted Mixed Nuts bar")["id"] == "usda-nuts"

    def test_match_stirfry_soy_sauce_does_not_collapse_to_pasta(self):
        # "noodle" is a pasta keyword; "chow mein noodles" should hit stir-fry's
        # longer "chow mein" keyword (longest-match wins), not pasta.
        assert match_usda_food("Chow Mein Noodle House")["id"] == "usda-stirfry"

    def test_no_match_returns_none(self):
        assert match_usda_food("Museum of Modern Art cafe") is None
        assert match_usda_food("") is None

    def test_longest_keyword_wins(self):
        # "rice porridge" (congee) beats generic "rice"-only rows via longest match.
        hit = match_usda_food("Rice Porridge Shop")
        assert hit is not None
        assert hit["id"] == "usda-congee"


class TestSodiumCheck:
    def test_pasta_low_sodium_passes(self):
        row = match_usda_food("spaghetti")
        ok, note = sodium_check(row)
        assert ok is True
        assert "Low sodium" in note and "1mg" in note

    def test_bacon_high_sodium_fails(self):
        row = match_usda_food("bacon")
        ok, note = sodium_check(row)
        assert ok is False
        assert "Sodium high" in note

    def test_tofu_passes(self):
        row = match_usda_food("tofu")
        ok, _ = sodium_check(row)
        assert ok is True

    def test_miso_soup_fails(self):
        row = match_usda_food("miso soup")
        ok, _ = sodium_check(row)
        assert ok is False


class TestTextureCheck:
    def test_soft(self):
        ok, note = texture_check(match_usda_food("congee"))
        assert ok is True
        assert "soft" in note

    def test_hard(self):
        ok, note = texture_check(match_usda_food("fried chicken"))
        assert ok is False
        assert "hard" in note

    def test_medium(self):
        ok, note = texture_check(match_usda_food("salmon"))
        assert ok is True
        assert "medium" in note


class TestAnnotateHealthUsdaIntegration:
    def test_usda_field_attached_when_matched(self):
        result = _annotate_health(
            {"name": "Congee House", "tags": ["porridge", "Chinese"], "description": ""},
            ["soft_chewable", "low_sodium"],
        )
        assert result["usda"] is not None
        assert result["usda"]["source"] == "usda-fdc"
        assert result["usda"]["per_100g"]["sodium_mg"] == 4

    def test_usda_none_when_no_match(self):
        result = _annotate_health(
            {"name": "Museum Cafe", "tags": [], "description": ""},
            ["low_sodium"],
        )
        assert result["usda"] is None
        # Keyword layer still produced a judgement (fallback stays intact).
        assert "passes" in result and "labels" in result

    def test_bacon_fails_low_sodium_with_usda_numbers(self):
        result = _annotate_health(
            {"name": "Bacon Bistro", "tags": ["american"], "description": ""},
            ["low_sodium"],
        )
        assert result["passes"] is False
        assert any("Sodium high" in w for w in result["warnings"])

    def test_soft_keeps_standard_label(self):
        result = _annotate_health(
            {"name": "Congee House", "tags": ["porridge"], "description": ""},
            ["soft_chewable"],
        )
        assert result["passes"] is True
        assert "Soft food friendly" in result["labels"]

    def test_hard_flagged_soft_constraint(self):
        result = _annotate_health(
            {"name": "Fried Chicken Joint", "tags": ["american"], "description": ""},
            ["soft_chewable"],
        )
        assert result["passes"] is False

    def test_soy_glazed_tofu_still_fails_sodium(self):
        # USDA says tofu is low sodium, but keyword layer flags the soy-glazed
        # seasoning — both layers run, FAIL wins (conservative screening).
        result = _annotate_health(
            {"name": "Soy-Glazed Tofu", "tags": ["asian"], "description": ""},
            ["low_sodium"],
        )
        assert result["passes"] is False

    def test_pure_tofu_passes_sodium(self):
        result = _annotate_health(
            {"name": "Steamed Tofu", "tags": ["healthy"], "description": ""},
            ["low_sodium"],
        )
        assert result["passes"] is True
        assert any("Low sodium" in lbl for lbl in result["labels"])


class TestMedicationBoundary:
    def test_medication_rules_still_handwritten_not_usda(self):
        # USDA table must NOT carry medication logic — the boundary holds.
        for food in load_usda_db()["foods"]:
            assert "medication" not in food
            assert "drug" not in food
            assert "interaction" not in food

    def test_med_rules_cover_key_interactions(self):
        # Existing handwritten whitelist remains the medication layer.
        assert "grapefruit" in _MED_RULES
        assert "vitamin_k" in _MED_RULES
        assert "tyramine" in _MED_RULES