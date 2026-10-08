from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.qloo.client import get_qloo_client
from app.services.qloo.tastecare import recommend_meals, MEDICATION_DISCLAIMER, DEFAULT_AGE_SIGNAL

router = APIRouter(prefix="/tastecare", tags=["tastecare"])


class SeniorProfile(BaseModel):
    cultural_likes: list[str] = Field(
        default_factory=list,
        description="文化偏好：菜系 / 艺术家 / 电影等，作为 Qloo 口味锚点",
    )
    cuisine_tags: list[str] = Field(
        default_factory=list,
        description="可选：Qloo 菜系 tag ID 列表（如 urn:tag:genre:... ）",
    )
    location: str | None = Field(default=None, description="地区/城市，如 'New York'")
    constraints: dict[str, Any] = Field(
        default_factory=dict,
        description="健康约束：{ low_sugar, low_sodium, soft_chewable, medications }",
    )
    take: int = Field(default=12, ge=1, le=50)


class TasteCareStatusResponse(BaseModel):
    enabled: bool
    base_url: str
    api_key_set: bool
    age_signal: str = DEFAULT_AGE_SIGNAL
    supported_constraints: list[str] = ["low_sugar", "low_sodium", "soft_chewable", "medications"]
    disclaimer: str = MEDICATION_DISCLAIMER


class TasteCareRecommendResponse(BaseModel):
    recommendations: list[dict[str, Any]] = Field(default_factory=list)
    source: str = "qloo"
    location: str | None = None
    active_constraints: list[str] = Field(default_factory=list)
    explanation: str = ""
    disclaimer: str = MEDICATION_DISCLAIMER


def _ensure_client():
    client = get_qloo_client()
    if not client.enabled:
        raise HTTPException(
            status_code=503,
            detail="Qloo API is not configured. Set QLOO_API_KEY environment variable.",
        )
    return client


@router.get("/status", response_model=TasteCareStatusResponse)
async def tastecare_status():
    client = get_qloo_client()
    return TasteCareStatusResponse(
        enabled=client.enabled,
        base_url=client.config.base_url,
        api_key_set=bool(client.config.api_key),
    )


@router.post("/recommend", response_model=TasteCareRecommendResponse)
async def tastecare_recommend(payload: SeniorProfile):
    client = _ensure_client()
    result = await recommend_meals(
        client,
        cultural_likes=payload.cultural_likes,
        location=payload.location,
        constraints=payload.constraints,
        cuisine_tags=payload.cuisine_tags,
        take=payload.take,
    )
    if result.get("error"):
        raise HTTPException(status_code=422, detail=result["error"])
    return TasteCareRecommendResponse(
        recommendations=result.get("recommendations", []),
        location=result.get("location"),
        active_constraints=result.get("active_constraints", []),
        explanation=result.get("explanation", ""),
    )
