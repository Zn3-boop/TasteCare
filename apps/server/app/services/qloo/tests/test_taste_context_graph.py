from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.llm.client import plan_steps_llm
from app.services.graph.nodes import planning_node


class TestPlanStepsLlmTasteContext:
    @pytest.mark.asyncio
    async def test_no_taste_context_no_block(self):
        with patch("app.services.llm.client.llm_parse_with_retry", new_callable=AsyncMock, return_value=(None, None)):
            is_multi, steps = await plan_steps_llm("帮我写一篇文章", "内容生成", "content_gen_agent_node")
            assert is_multi is False
            assert steps == []

    @pytest.mark.asyncio
    async def test_taste_context_injected_into_prompt(self):
        captured_prompt = None

        async def fake_llm_parse(prompt, schema_cls, **kw):
            nonlocal captured_prompt
            captured_prompt = prompt
            return None, None

        taste_ctx = "[Qloo] Maria likes Jazz, Italian dining, classic films"
        with patch("app.services.llm.client.llm_parse_with_retry", side_effect=fake_llm_parse):
            await plan_steps_llm(
                "给Maria推荐晚餐",
                "餐饮推荐",
                "qloo_cultural_recommend_node",
                taste_context=taste_ctx,
            )
        assert captured_prompt is not None
        assert "[Qloo文化智能背景]" in captured_prompt
        assert "Maria likes Jazz" in captured_prompt
        assert "[/Qloo文化智能背景]" in captured_prompt

    @pytest.mark.asyncio
    async def test_empty_taste_context_no_block_injected(self):
        captured_prompt = None

        async def fake_llm_parse(prompt, schema_cls, **kw):
            nonlocal captured_prompt
            captured_prompt = prompt
            return None, None

        with patch("app.services.llm.client.llm_parse_with_retry", side_effect=fake_llm_parse):
            await plan_steps_llm(
                "帮我写一篇文章",
                "内容生成",
                "content_gen_agent_node",
                taste_context="",
            )
        assert captured_prompt is not None
        assert "[Qloo文化智能背景]" not in captured_prompt


class TestPlanningNodeTasteContext:
    @pytest.mark.asyncio
    async def test_planning_node_passes_taste_context(self):
        captured_kwargs = None

        async def fake_plan_steps(raw_query, intent, route_target, **kw):
            nonlocal captured_kwargs
            captured_kwargs = kw
            return False, []

        state = {
            "raw_query": "给Maria推荐晚餐",
            "intent": "餐饮推荐",
            "route_target": "qloo_cultural_recommend_node",
            "qloo_taste_context": "[Qloo] Jazz + Italian dining",
        }

        with patch("app.services.graph.nodes.LLM_MODE", "real"):
            with patch("app.services.llm.client.plan_steps_llm", side_effect=fake_plan_steps):
                result = await planning_node(state)

        assert captured_kwargs is not None
        assert captured_kwargs.get("taste_context") == "[Qloo] Jazz + Italian dining"

    @pytest.mark.asyncio
    async def test_planning_node_no_taste_context_passes_empty(self):
        captured_kwargs = None

        async def fake_plan_steps(raw_query, intent, route_target, **kw):
            nonlocal captured_kwargs
            captured_kwargs = kw
            return False, []

        state = {
            "raw_query": "帮我写一篇文章",
            "intent": "内容生成",
            "route_target": "content_gen_agent_node",
            "qloo_taste_context": "",
        }

        with patch("app.services.graph.nodes.LLM_MODE", "real"):
            with patch("app.services.llm.client.plan_steps_llm", side_effect=fake_plan_steps):
                result = await planning_node(state)

        assert captured_kwargs is not None
        assert captured_kwargs.get("taste_context") == ""