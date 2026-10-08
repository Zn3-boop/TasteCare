from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from app.services.qloo.config import QlooConfig
from app.services.qloo.client import QlooClient


@pytest.fixture
def qloo_config():
    return QlooConfig(
        api_key="test-key-123",
        base_url="https://hackathon.api.qloo.com",
        timeout_seconds=10,
        max_retries=2,
    )


@pytest.fixture
def qloo_client(qloo_config):
    return QlooClient(config=qloo_config)


def test_config_from_env():
    with patch.dict("os.environ", {"QLOO_API_KEY": "env-key", "QLOO_BASE_URL": "https://custom.api.com"}):
        config = QlooConfig.from_env()
        assert config.api_key == "env-key"
        assert config.base_url == "https://custom.api.com"
        assert config.enabled is True


def test_config_default_base_url_is_hackathon():
    with patch.dict("os.environ", {"QLOO_API_KEY": "k"}, clear=False):
        config = QlooConfig.from_env()
        assert config.base_url == "https://hackathon.api.qloo.com"


def test_config_disabled_when_no_key():
    with patch.dict("os.environ", {"QLOO_API_KEY": ""}):
        config = QlooConfig.from_env()
        assert config.enabled is False


def test_client_enabled(qloo_client):
    assert qloo_client.enabled is True


def test_client_disabled():
    config = QlooConfig(api_key="", base_url="https://hackathon.api.qloo.com", timeout_seconds=10, max_retries=2)
    client = QlooClient(config=config)
    assert client.enabled is False


@pytest.mark.asyncio
async def test_search_builds_types_and_take(qloo_client):
    mock_response = {
        "success": True,
        "results": {
            "entities": [
                {"name": "Radiohead", "entity_id": "E1", "subtype": "urn:entity:artist"},
                {"name": "Pink Floyd", "entity_id": "E2", "subtype": "urn:entity:artist"},
            ]
        },
    }
    with patch.object(qloo_client, "_request", new_callable=AsyncMock, return_value=mock_response) as mock_req:
        result = await qloo_client.search("Radiohead", entity_types=["urn:entity:artist"], take=2)
        # _request called with GET /search and params
        _args, _kwargs = mock_req.call_args
        assert _args[0] == "GET"
        assert _args[1] == "/search"
        assert _kwargs["params"]["types"] == "urn:entity:artist"
        assert _kwargs["params"]["take"] == 2
        assert len(result["results"]["entities"]) == 2


@pytest.mark.asyncio
async def test_insights_builds_filter_and_signals(qloo_client):
    mock_response = {"success": True, "results": {"entities": [{"name": "Muse", "entity_id": "E3", "subtype": "urn:entity:artist"}]}}
    with patch.object(qloo_client, "_request", new_callable=AsyncMock, return_value=mock_response) as mock_req:
        result = await qloo_client.insights(
            filter_type="urn:entity:artist",
            signal_entities=["E1"],
            take=5,
        )
        _args, _kwargs = mock_req.call_args
        assert _args[1] == "/v2/insights"
        assert _kwargs["params"]["filter.type"] == "urn:entity:artist"
        assert _kwargs["params"]["signal.interests.entities"] == "E1"
        assert _kwargs["params"]["take"] == 5
        assert result["results"]["entities"][0]["name"] == "Muse"


@pytest.mark.asyncio
async def test_insights_cross_domain_filters(qloo_client):
    mock_response = {"success": True, "results": {"entities": []}}
    with patch.object(qloo_client, "_request", new_callable=AsyncMock, return_value=mock_response) as mock_req:
        await qloo_client.insights(
            filter_type="urn:entity:place",
            signal_entities=["E1"],
            location_query="New York",
            filters={"filter.price_level.max": 2, "filter.popularity.min": 0.5},
            demographics_age="55_and_older",
            take=8,
        )
        _args, _kwargs = mock_req.call_args
        params = _kwargs["params"]
        assert params["filter.type"] == "urn:entity:place"
        assert params["filter.location.query"] == "New York"
        assert params["filter.price_level.max"] == 2
        assert params["filter.popularity.min"] == 0.5
        assert params["signal.demographics.age"] == "55_and_older"


@pytest.mark.asyncio
async def test_request_error_handling(qloo_client):
    with patch.object(qloo_client, "_request", new_callable=AsyncMock, return_value={"error": "auth_failed", "detail": "status=401"}):
        result = await qloo_client.search("test")
        assert "error" in result
        assert result["error"] == "auth_failed"
