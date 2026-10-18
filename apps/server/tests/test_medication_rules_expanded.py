from __future__ import annotations
import sys
from pathlib import Path
import pytest
_SERVER_DIR = Path(__file__).resolve().parent.parent
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))
from app.services.qloo.tastecare import _MED_RULES, _annotate_medication
class TestMedicationRulesExpanded:
    REQUIRED_RULES = ["grapefruit", "vitamin_k", "alcohol", "tyramine", "licorice", "warfarin_green_tea", "ace_inhibitor_potassium", "maoi_cheese"]
    def test_all_required_rules_exist(self):
        for rule_name in self.REQUIRED_RULES:
            assert rule_name in _MED_RULES, f"Missing medication rule: {rule_name}"
    def test_grapefruit_keywords_triggered(self):
        result = _annotate_medication({"name": "Grapefruit Salad", "tags": ["citrus"]}, ["medications"])
        assert any("grapefruit" in w.lower() or "citrus" in w.lower() for w in result.get("warnings", []))
    def test_vitamin_k_leafy_greens_triggered(self):
        result = _annotate_medication({"name": "Kale Salad", "tags": ["leafy green"]}, ["medications"])
        assert any("vitamin k" in w.lower() or "kale" in w.lower() for w in result.get("warnings", []))
    def test_alcohol_flagged(self):
        result = _annotate_medication({"name": "Beef Stroganoff with Wine Sauce", "tags": []}, ["medications"])
        assert any("alcohol" in w.lower() or "wine" in w.lower() for w in result.get("warnings", []))
    def test_tyramine_cheese_triggered(self):
        result = _annotate_medication({"name": "Aged Cheddar Cheese Platter", "tags": ["aged cheese"]}, ["medications"])
        assert any("tyramine" in w.lower() or "cheese" in w.lower() for w in result.get("warnings", []))
    def test_no_medications_constraint_skips_screening(self):
        result = _annotate_medication({"name": "Spam and Eggs", "tags": []}, [])
        assert result.get("warnings") == []
    def test_multiple_interactions_accumulated(self):
        result = _annotate_medication({"name": "Kale with Spinach", "tags": ["leafy green", "spinach"]}, ["medications"])
        assert len(result.get("warnings", [])) >= 1
class TestWarfarinGreenTeaRule:
    def test_green_tea_triggers_warning(self):
        result = _annotate_medication({"name": "Green Tea Ice Cream", "tags": ["green tea"]}, ["medications"])
        assert any("warfarin" in w.lower() or "green tea" in w.lower() for w in result.get("warnings", []))
    def test_match_is_case_insensitive(self):
        result = _annotate_medication({"name": "MATCHA LATTE", "tags": ["Matcha"]}, ["medications"])
        assert any("warfarin" in w.lower() or "matcha" in w.lower() or "green tea" in w.lower() for w in result.get("warnings", []))
class TestACEInhibitorPotassiumRule:
    def test_banana_triggers_warning(self):
        result = _annotate_medication({"name": "Banana Smoothie", "tags": ["banana"]}, ["medications"])
        assert any("potassium" in w.lower() or "banana" in w.lower() for w in result.get("warnings", []))
    def test_avocado_triggers_warning(self):
        result = _annotate_medication({"name": "Avocado Toast", "tags": ["avocado"]}, ["medications"])
        assert any("potassium" in w.lower() or "avocado" in w.lower() for w in result.get("warnings", []))
class TestMAOICheeseRule:
    def test_aged_cheese_triggers_warning(self):
        result = _annotate_medication({"name": "Brie and Crackers", "tags": ["aged cheese"]}, ["medications"])
        assert any("maoi" in w.lower() or "cheese" in w.lower() for w in result.get("warnings", []))
    def test_soysauce_triggers_warning(self):
        result = _annotate_medication({"name": "Pad Thai with Soy Sauce", "tags": ["soy sauce"]}, ["medications"])
        assert any("maoi" in w.lower() or "soy" in w.lower() for w in result.get("warnings", []))