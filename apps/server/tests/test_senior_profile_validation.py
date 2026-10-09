"""SeniorProfile Pydantic validation tests.

Locks the /tastecare/recommend request contract:

  * take: default 12, must be 1..50 (reject 0, 51, negative)
  * cultural_likes: default []
  * cuisine_tags: default []
  * location: optional str, default None
  * constraints: free-form dict (low_sodium / medications / ...), default {}

Also verifies the same bounds surface as HTTP 422s on the live route (FastAPI
validation runs before the handler, so no Qloo client is needed to prove the
rejection).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

_SERVER_DIR = Path(__file__).resolve().parent.parent
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))

from app.api.tastecare import SeniorProfile  # noqa: E402
from app.main import app  # noqa: E402

client_http = TestClient(app)


# ═══════════════════════════════════════════════════════════════════════════
# 1. take — bounds & default
# ═══════════════════════════════════════════════════════════════════════════

class TestTakeValidation:
    def test_default_take_is_12(self):
        assert SeniorProfile().take == 12

    def test_take_1_accepted(self):
        assert SeniorProfile(take=1).take == 1

    def test_take_50_accepted(self):
        assert SeniorProfile(take=50).take == 50

    @pytest.mark.parametrize("bad", [0, -1, 51, 100])
    def test_out_of_bounds_take_rejected(self, bad):
        with pytest.raises(ValidationError):
            SeniorProfile(take=bad)

    @pytest.mark.parametrize("bad", [12.5, None, []])
    def test_non_integer_take_rejected(self, bad):
        with pytest.raises(ValidationError):
            SeniorProfile(take=bad)


# ═══════════════════════════════════════════════════════════════════════════
# 2. Defaults — cultural_likes / cuisine_tags / location / constraints
# ═══════════════════════════════════════════════════════════════════════════

class TestDefaults:
    def test_cultural_likes_default_empty_list(self):
        assert SeniorProfile().cultural_likes == []

    def test_cultural_likes_preserved(self):
        assert SeniorProfile(cultural_likes=["Jazz", "Italian"]).cultural_likes == [
            "Jazz",
            "Italian",
        ]

    def test_cuisine_tags_default_empty_list(self):
        assert SeniorProfile().cuisine_tags == []

    def test_cuisine_tags_preserved(self):
        assert SeniorProfile(cuisine_tags=["urn:tag:cuisine:qloo:italian"]).cuisine_tags == [
            "urn:tag:cuisine:qloo:italian"
        ]

    def test_location_default_none(self):
        assert SeniorProfile().location is None

    def test_location_string_accepted(self):
        assert SeniorProfile(location="New York").location == "New York"

    def test_constraints_default_empty_dict(self):
        assert SeniorProfile().constraints == {}


# ═══════════════════════════════════════════════════════════════════════════
# 3. constraints — free-form schema
# ═══════════════════════════════════════════════════════════════════════════

class TestConstraintsSchema:
    def test_bool_flags_accepted(self):
        p = SeniorProfile(constraints={"low_sodium": True, "low_sugar": False})
        assert p.constraints["low_sodium"] is True
        assert p.constraints["low_sugar"] is False

    def test_medications_list_accepted(self):
        p = SeniorProfile(constraints={"medications": ["warfarin", "statins"]})
        assert p.constraints["medications"] == ["warfarin", "statins"]

    def test_arbitrary_unknown_keys_kept(self):
        # The schema is deliberately open so the health-extraction layer can add
        # new rule keys without an API migration.
        p = SeniorProfile(constraints={"custom_rule": {"min": 0.5}})
        assert p.constraints["custom_rule"] == {"min": 0.5}

    def test_complex_mixed_constraints(self):
        p = SeniorProfile(
            constraints={
                "low_sodium": True,
                "soft_chewable": True,
                "medications": ["statins", "warfarin"],
            }
        )
        assert set(p.constraints) == {"low_sodium", "soft_chewable", "medications"}


# ═══════════════════════════════════════════════════════════════════════════
# 4. HTTP surface — 422 before the handler for invalid take
# ═══════════════════════════════════════════════════════════════════════════

class TestSeniorProfileHTTP:
    def _disabled_client(self):
        from unittest.mock import MagicMock

        c = MagicMock()
        c.enabled = False
        return c

    @pytest.mark.parametrize("bad_take", [0, -1, 51, 100])
    def test_invalid_take_returns_422(self, bad_take):
        resp = client_http.post(
            "/api/v1/tastecare/recommend",
            json={"cultural_likes": ["Jazz"], "take": bad_take},
        )
        assert resp.status_code == 422, resp.text
        assert "take" in resp.text

    def test_valid_take_reaches_handler(self):
        # take=50 passes validation; the handler then 503s on the disabled client
        # — proving validation did NOT block it. (Client is mocked so this stays
        # deterministic regardless of whether QLOO_API_KEY is set locally.)
        from unittest.mock import patch

        with patch("app.api.tastecare.get_qloo_client", return_value=self._disabled_client()):
            resp = client_http.post(
                "/api/v1/tastecare/recommend",
                json={"cultural_likes": ["Jazz"], "take": 50},
            )
        assert resp.status_code == 503

    def test_default_take_reaches_handler(self):
        # No take -> default 12 -> validation passes -> handler 503 (disabled mock).
        from unittest.mock import patch

        with patch("app.api.tastecare.get_qloo_client", return_value=self._disabled_client()):
            resp = client_http.post(
                "/api/v1/tastecare/recommend",
                json={"cultural_likes": ["Jazz"]},
            )
        assert resp.status_code == 503

    def test_malformed_constraints_returns_422(self):
        resp = client_http.post(
            "/api/v1/tastecare/recommend",
            json={"cultural_likes": ["Jazz"], "constraints": "low_sodium"},
        )
        assert resp.status_code == 422

    def test_malformed_cultural_likes_returns_422(self):
        resp = client_http.post(
            "/api/v1/tastecare/recommend",
            json={"cultural_likes": "Jazz"},
        )
        assert resp.status_code == 422
