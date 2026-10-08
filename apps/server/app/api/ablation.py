"""Ablation comparison API — powers the web demo's Ablation tab.

Contract (matches apps/web/src/api.ts AblationComparisonResponse):
  POST /ablation/comparison
  -> {
       timestamp: number,
       cases: unknown[],
       variants: Record<string, AblationVariantResult[]>,
       comparison: [{ case, variant_a, variant_b }],
       data_source: 'live' | 'preview',
     }
Each variant result: { top_pick, has_cultural_match, cultural_grounding,
data_source, rationale: [{name, cultural_match, safety_validation, passes}] }
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.eval.ablation import run_ablation_comparison

router = APIRouter(prefix="/ablation", tags=["ablation"])


class AblationComparisonRequest(BaseModel):
    """Empty body for now — comparison runs over built-in demo cases."""
    pass  # noqa: E701


class AblationComparisonResponse(BaseModel):
    timestamp: float
    cases: list[dict[str, Any]] = []
    variants: dict[str, list[dict[str, Any]]] = {}
    comparison: list[dict[str, Any]] = []
    data_source: str = "preview"


@router.post("/comparison", response_model=AblationComparisonResponse)
async def ablation_comparison(payload: AblationComparisonRequest | None = None) -> AblationComparisonResponse:
    """Run the paired Variant A / Variant B comparison over demo senior-dining cases."""
    from app.services.qloo.client import get_qloo_client

    client = get_qloo_client()
    result = await run_ablation_comparison(client)
    return AblationComparisonResponse(**result)
