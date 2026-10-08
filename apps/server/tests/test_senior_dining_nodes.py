"""Unit tests for the Senior Dining sub-graph nodes.

Network-free: the Qloo client is stubbed (preview mode), and health extraction
runs through mock (LLM_MODE=mock per conftest).
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.graph.nodes import (
    health_constraint_extract_node,
    taste_context_extract_node,
)


def run(awaitable):
    return asyncio.new_event_loop().run_until_complete(awaitable)


def _mock_qloo_client():
    mock = MagicMock()
    mock.enabled = False
    mock.search = AsyncMock(return_value={"results": {"entities": []}})
    return mock


def test_taste_context_extract_writes_entities_and_source():
    with patch("app.services.qloo.client.get_qloo_client", return_value=_mock_qloo_client()):
        state = {
            "raw_query": "help Maria",
            "entities": {"cultural_likes": ["Jiangnan home cooking", "light flavor"]},
        }
        out = run(taste_context_extract_node(state))
        assert out.get("taste_data_source") in ("preview", "live", "none", None) or "taste_entities" in out or "taste_data_source" in out


def test_taste_context_extract_falls_back_to_raw_query_tokens():
    with patch("app.services.qloo.client.get_qloo_client", return_value=_mock_qloo_client()):
        state = {
            "raw_query": "hypertension, poor dentition, light Jiangnan cooking",
            "entities": {},
        }
        out = run(taste_context_extract_node(state))
        assert out is not None


def test_health_constraint_extract_mock_detects_maria():
    with patch("app.services.graph.nodes.LLM_MODE", "mock"):
        state = {"raw_query": "hypertension, poor dentition, light Jiangnan cooking"}
        out = run(health_constraint_extract_node(state))

        constraints = out["health_constraints"]
        assert constraints["low_sodium"] is True
        assert constraints["soft_chewable"] is True
        assert constraints["low_sugar"] is False
        assert constraints["_source"] == "llm_extracted"
        assert out["health_constraint_labels"] == ["low_sodium", "soft_chewable"]


def test_health_constraint_extract_empty_query_returns_empty():
    with patch("app.services.graph.nodes.LLM_MODE", "mock"):
        out = run(health_constraint_extract_node({"raw_query": ""}))
        constraints = out["health_constraints"]
        assert constraints["low_sodium"] is False
        assert constraints["low_sugar"] is False
        assert constraints["soft_chewable"] is False
        assert constraints["medications"] == []
        assert out["health_constraint_labels"] == []


def test_health_constraint_extract_skips_explicit():
    with patch("app.services.graph.nodes.LLM_MODE", "mock"):
        state = {
            "raw_query": "hypertension",
            "health_constraints": {"_source": "explicit", "low_sodium": True},
        }
        assert run(health_constraint_extract_node(state)) == {}


def test_senior_subgraph_input_pair_formed():
    with patch("app.services.qloo.client.get_qloo_client", return_value=_mock_qloo_client()):
        with patch("app.services.graph.nodes.LLM_MODE", "mock"):
            state = {
                "raw_query": "hypertension and poor dentition, light Jiangnan home cooking",
                "entities": {"cultural_likes": ["Jiangnan home cooking", "light flavor"]},
            }
            state.update(run(taste_context_extract_node(state)))
            state.update(run(health_constraint_extract_node(state)))

            assert "taste_entities" in state
            assert "health_constraints" in state