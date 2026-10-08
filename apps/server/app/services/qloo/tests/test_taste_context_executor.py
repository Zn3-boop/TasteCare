from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock


class TestQlooTasteContextExecutor:
    @pytest.mark.asyncio
    async def test_search_cultural_entities(self):
        from app.services.qloo.taste import search_cultural_entities
        from app.services.qloo.client import QlooClient

        mock_client = MagicMock(spec=QlooClient)
        mock_client.enabled = False
        mock_client.search = AsyncMock(return_value={"results": {"entities": []}})
        result = await search_cultural_entities(mock_client, query="Jazz")
        assert result is not None

    @pytest.mark.asyncio
    async def test_build_cultural_context_preview_mode(self):
        from app.services.qloo.taste import build_cultural_context_for_llm
        from app.services.qloo.client import QlooClient

        mock_client = MagicMock(spec=QlooClient)
        mock_client.enabled = False
        result = await build_cultural_context_for_llm(mock_client, user_likes=["Sinatra", "Jazz"])
        assert result is not None