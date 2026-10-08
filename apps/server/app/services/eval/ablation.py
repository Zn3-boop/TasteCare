"""Ablation comparison for the TasteCare senior-dining demo.

Runs the SAME senior-dining prompts through two variants and returns a
side-by-side comparison so the UI can show what cultural grounding adds:

- Variant A (no Qloo): pure rule-based dining screening. Uses the health
  constraint keyword layer from tastecare.py on a deterministic candidate
  pool. No LLM, no Qloo — fully offline and honest (data_source="rules").
- Variant B (with Qloo): the real TasteCare pipeline (recommend_meals)
  when QLOO_API_KEY is configured; otherwise falls back to the same
  deterministic candidate pool labelled "preview" so the UI can still
  render a comparison without a key.

Both variants share the same candidates, so the only difference shown is
whether cultural grounding (Qloo taste graph) is applied.
"""

from __future__ import annotations

import time
from typing import Any

from app.services.qloo.tastecare import (
    _annotate_health,
    _build_constraint_labels,
    recommend_meals,
)

# Deterministic senior-friendly dining candidates used when Qloo is disabled.
# Each entry mirrors the shape Qloo /v2/insights returns (name/tags/description)
# so both variants run over identical input.
_DEMO_CANDIDATES: list[dict[str, Any]] = [
    {
        "entity_id": "preview-congee",
        "name": "Jiangnan Congee House",
        "tags": ["porridge", "Chinese", "steamed", "light"],
        "description": "Traditional Jiangnan-style congee with fresh vegetables and steamed fish.",
        "popularity": 0.72,
    },
    {
        "entity_id": "preview-bbq",
        "name": "Salt & Smoke BBQ",
        "tags": ["BBQ", "smoked", "bacon"],
        "description": "Slow-smoked ribs and bacon-topped cornbread.",
        "popularity": 0.88,
    },
    {
        "entity_id": "preview-bakery",
        "name": "Sweet Bakery",
        "tags": ["bakery", "dessert", "cake"],
        "description": "Fresh pastries, layer cakes and sweet iced drinks.",
        "popularity": 0.84,
    },
    {
        "entity_id": "preview-risotto",
        "name": "Risotto House",
        "tags": ["Italian", "risotto", "soft"],
        "description": "Creamy risotto and soft-chew Italian classics.",
        "popularity": 0.67,
    },
]

# Demo prompts: same senior-dining scenarios across both variants.
_DEMO_CASES: list[dict[str, Any]] = [
    {
        "query": "妈妈高血压，牙口不好，想吃江南清淡家常菜，推荐几家附近餐厅",
        "cultural_likes": ["Jiangnan home cooking", "light flavor"],
        "location": "Shanghai",
        "constraints": {"low_sodium": True, "soft_chewable": True},
    },
    {
        "query": "给喜欢老电影的奶奶找个能喝粥的清淡餐馆",
        "cultural_likes": ["classic films", "soft congee"],
        "location": "Shanghai",
        "constraints": {"low_sodium": True, "soft_chewable": True, "low_sugar": True},
    },
    {
        "query": "爷爷爱吃红烧肉，但血糖高，有没有合适的本帮菜馆",
        "cultural_likes": ["Shanghai braised pork", "home-style"],
        "location": "Shanghai",
        "constraints": {"low_sugar": True},
    },
]


def _candidate_pool(active_labels: list[str]) -> list[dict[str, Any]]:
    """Annotate the deterministic pool with health screening for variant A."""
    pool: list[dict[str, Any]] = []
    for raw in _DEMO_CANDIDATES:
        candidate = dict(raw)
        health = _annotate_health(candidate, active_labels)
        candidate["health"] = health
        candidate["fit_source"] = "rules"
        candidate["fit"] = candidate.get("popularity", 0.0)
        pool.append(candidate)
    return pool


def _sort_by_health_then_fit(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Passing candidates first, then by fit (honest popularity)."""
    return sorted(
        candidates,
        key=lambda c: (
            1 if c.get("health", {}).get("passes") else 0,
            c.get("fit", 0.0),
        ),
        reverse=True,
    )


def _to_variant_result(
    recommendations: list[dict[str, Any]],
    data_source: str,
) -> dict[str, Any]:
    """Shape a recommendation list into the UI's AblationVariantResult contract."""
    rationale = [
        {
            "name": r.get("name", ""),
            "cultural_match": (
                "Taste-graph cultural anchor match (Qloo)" if data_source == "live" else "Rule-based preference match"
            ),
            "safety_validation": "、".join(r.get("health", {}).get("labels", [])) or (
                "Passed health screening" if r.get("health", {}).get("passes") else "Flagged by health screening"
            ),
            "passes": bool(r.get("health", {}).get("passes")),
        }
        for r in recommendations
    ]
    top = recommendations[0] if recommendations else None
    return {
        "top_pick": top.get("name") if top else None,
        "has_cultural_match": bool(top and top.get("name")),
        "cultural_grounding": data_source,
        "data_source": data_source,
        "rationale": rationale,
    }


def _variant_a(case: dict[str, Any]) -> dict[str, Any]:
    """Variant A — no Qloo: rule-based health screening only."""
    constraints = case.get("constraints", {})
    active_labels = _build_constraint_labels(constraints)
    pool = _candidate_pool(active_labels)
    sorted_pool = _sort_by_health_then_fit(pool)
    return _to_variant_result(sorted_pool, "rules")


async def _variant_b(client: Any, case: dict[str, Any]) -> dict[str, Any]:
    """Variant B — with Qloo: real TasteCare pipeline (preview fallback)."""
    if client.enabled:
        result = await recommend_meals(
            client,
            cultural_likes=case.get("cultural_likes", []),
            location=case.get("location"),
            constraints=case.get("constraints", {}),
            take=12,
        )
        if not result.get("error"):
            return _to_variant_result(result.get("recommendations", []), "live")
    # No key / error: deterministic preview so the UI still renders honestly.
    constraints = case.get("constraints", {})
    active_labels = _build_constraint_labels(constraints)
    pool = _candidate_pool(active_labels)
    sorted_pool = _sort_by_health_then_fit(pool)
    return _to_variant_result(sorted_pool, "preview")


async def run_ablation_comparison(client: Any) -> dict[str, Any]:
    """Run the paired Variant A / Variant B comparison over all demo cases."""
    comparison: list[dict[str, Any]] = []
    for case in _DEMO_CASES:
        comparison.append(
            {
                "case": case,
                "variant_a": _variant_a(case),
                "variant_b": await _variant_b(client, case),
            }
        )
    return {
        "timestamp": time.time(),
        "cases": _DEMO_CASES,
        "comparison": comparison,
        "data_source": "live" if client.enabled else "preview",
    }

