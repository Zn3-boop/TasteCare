"""Tests for prompts.py — the LLM context templates that ground agent output
in Qloo cultural taste data.

These tests lock the two properties the templates exist to guarantee:

  * non-generic grounding — every prompt must reference Qloo taste data
    (250M+ entity graph, taste scores, cross-domain connections) and forbid
    falling back to generic LLM knowledge;
  * placeholder hygiene — every template renders via .format() without leaving
    unsubstituted `{...}` placeholders behind.

No network / no LLM calls are made in this file.
"""

from __future__ import annotations

import pytest

from app.services.qloo import prompts as P


# ═══════════════════════════════════════════════════════════════════════════
# 1. System prompt — the "culturally intelligent agent" contract
# ═══════════════════════════════════════════════════════════════════════════

class TestSystemPrompt:
    def test_mentions_qloo_taste_graph_and_scale(self):
        assert "Qloo" in P.CULTURAL_RECOMMENDATION_SYSTEM_PROMPT
        assert "250M+" in P.CULTURAL_RECOMMENDATION_SYSTEM_PROMPT
        assert "taste graph" in P.CULTURAL_RECOMMENDATION_SYSTEM_PROMPT

    def test_knowledge_is_grounded_not_guessed(self):
        assert "you don't guess" in P.CULTURAL_RECOMMENDATION_SYSTEM_PROMPT
        assert "you KNOW" in P.CULTURAL_RECOMMENDATION_SYSTEM_PROMPT
        assert "real cultural taste data" in P.CULTURAL_RECOMMENDATION_SYSTEM_PROMPT

    def test_domains_are_named(self):
        text = P.CULTURAL_RECOMMENDATION_SYSTEM_PROMPT
        for domain in ("music", "film", "dining", "fashion", "travel"):
            assert domain in text, f"expected domain {domain} in system prompt"

    def test_explain_why_rule(self):
        assert "taste similarity" in P.CULTURAL_RECOMMENDATION_SYSTEM_PROMPT
        assert "not just \"it's popular\"" in P.CULTURAL_RECOMMENDATION_SYSTEM_PROMPT

    def test_no_generic_llm_fallback(self):
        text = P.CULTURAL_RECOMMENDATION_SYSTEM_PROMPT
        assert "generic LLM" in text
        assert "If Qloo data is unavailable" in text
        assert "explicitly say so" in text

    def test_key_principle_wording(self):
        assert "Without Qloo, you would be guessing" in P.CULTURAL_RECOMMENDATION_SYSTEM_PROMPT
        assert "With Qloo, you are culturally grounded" in P.CULTURAL_RECOMMENDATION_SYSTEM_PROMPT

    def test_no_unformatted_placeholders(self):
        assert "{" not in P.CULTURAL_RECOMMENDATION_SYSTEM_PROMPT
        assert "}" not in P.CULTURAL_RECOMMENDATION_SYSTEM_PROMPT


# ═══════════════════════════════════════════════════════════════════════════
# 2. Context injection — injects the live Qloo block into the LLM context
# ═══════════════════════════════════════════════════════════════════════════

class TestContextInjection:
    def test_renders_injected_context(self):
        rendered = P.CULTURAL_CONTEXT_INJECTION.format(
            qloo_context="[Qloo] Jazz -> supper club, Italian dining -> trattoria"
        )
        assert "[Qloo Cultural Context]" in rendered
        assert "Jazz -> supper club" in rendered
        assert "Italian dining -> trattoria" in rendered

    def test_grounding_language_present(self):
        rendered = P.CULTURAL_CONTEXT_INJECTION.format(qloo_context="x")
        assert "250M+" in rendered
        assert "not generic LLM outputs" in rendered
        assert "taste-based suggestions" in rendered

    def test_no_unformatted_placeholders_after_render(self):
        rendered = P.CULTURAL_CONTEXT_INJECTION.format(qloo_context="x")
        assert "{" not in rendered
        assert "}" not in rendered


# ═══════════════════════════════════════════════════════════════════════════
# 3. Clarification prompt — one focused cultural question
# ═══════════════════════════════════════════════════════════════════════════

class TestClarificationPrompt:
    def test_renders_both_fields(self):
        rendered = P.CLARIFICATION_PROMPT_CULTURAL.format(
            current_understanding="senior in NYC likes light flavors",
            missing_info="preferred cuisine",
        )
        assert "senior in NYC likes light flavors" in rendered
        assert "preferred cuisine" in rendered

    def test_asks_exactly_one_question(self):
        assert "ONE focused question" in P.CLARIFICATION_PROMPT_CULTURAL
        assert "(not multiple)" in P.CLARIFICATION_PROMPT_CULTURAL

    def test_grounded_in_taste_graph(self):
        assert "taste graph" in P.CLARIFICATION_PROMPT_CULTURAL
        assert "taste-based recommendations" in P.CLARIFICATION_PROMPT_CULTURAL

    def test_no_unformatted_placeholders_after_render(self):
        rendered = P.CLARIFICATION_PROMPT_CULTURAL.format(
            current_understanding="u", missing_info="m"
        )
        assert "{" not in rendered
        assert "}" not in rendered
# ═══════════════════════════════════════════════════════════════════════════
# 4. Cross-domain bridge — connects two taste domains with WHY
# ═══════════════════════════════════════════════════════════════════════════

class TestCrossDomainBridge:
    def test_renders_all_four_fields(self):
        rendered = P.CROSS_DOMAIN_BRIDGE_PROMPT.format(
            source_domain="music",
            target_domain="dining",
            preferences="Jazz, Sinatra, Ella Fitzgerald",
            qloo_recommendations="jazz supper clubs in NYC",
        )
        assert "music" in rendered
        assert "dining" in rendered
        assert "Jazz, Sinatra, Ella Fitzgerald" in rendered
        assert "jazz supper clubs in NYC" in rendered

    def test_cultural_bridge_language(self):
        text = P.CROSS_DOMAIN_BRIDGE_PROMPT
        assert "cultural bridge" in text
        assert "taste similarity" in text
        assert "aesthetic, thematic, or atmospheric" in text

    def test_no_unformatted_placeholders_after_render(self):
        rendered = P.CROSS_DOMAIN_BRIDGE_PROMPT.format(
            source_domain="a", target_domain="b", preferences="c", qloo_recommendations="d"
        )
        assert "{" not in rendered
        assert "}" not in rendered


# ═══════════════════════════════════════════════════════════════════════════
# 5. Taste profile summary — concise cultural identity, not a list
# ═══════════════════════════════════════════════════════════════════════════

class TestTasteProfileSummary:
    def test_renders_profile_and_affinities(self):
        rendered = P.TASTE_PROFILE_SUMMARY_PROMPT.format(
            taste_profile="loves classic jazz and Italian dining",
            affinities="Sinatra -> jazz clubs, Neapolitan trattorias",
        )
        assert "loves classic jazz and Italian dining" in rendered
        assert "Sinatra -> jazz clubs, Neapolitan trattorias" in rendered

    def test_concise_insightful_instruction(self):
        assert "2-3 sentences" in P.TASTE_PROFILE_SUMMARY_PROMPT
        assert "aesthetic sensibility" in P.TASTE_PROFILE_SUMMARY_PROMPT

    def test_grounded_in_qloo_data(self):
        assert "Qloo data" in P.TASTE_PROFILE_SUMMARY_PROMPT

    def test_no_unformatted_placeholders_after_render(self):
        rendered = P.TASTE_PROFILE_SUMMARY_PROMPT.format(
            taste_profile="a", affinities="b"
        )
        assert "{" not in rendered
        assert "}" not in rendered


# ═══════════════════════════════════════════════════════════════════════════
# 6. Cross-cutting — every exported prompt renders without KeyError
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize(
    "template,kwargs",
    [
        (P.CULTURAL_RECOMMENDATION_SYSTEM_PROMPT, {}),
        (P.CULTURAL_CONTEXT_INJECTION, {"qloo_context": "ctx"}),
        (
            P.CLARIFICATION_PROMPT_CULTURAL,
            {"current_understanding": "u", "missing_info": "m"},
        ),
        (
            P.CROSS_DOMAIN_BRIDGE_PROMPT,
            {"source_domain": "a", "target_domain": "b", "preferences": "c", "qloo_recommendations": "d"},
        ),
        (P.TASTE_PROFILE_SUMMARY_PROMPT, {"taste_profile": "a", "affinities": "b"}),
    ],
)
def test_all_templates_render_without_missing_keys(template: str, kwargs: dict):
    rendered = template.format(**kwargs) if kwargs else template
    assert isinstance(rendered, str)
    assert len(rendered) > 0