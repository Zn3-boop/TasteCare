from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.qloo.client import get_qloo_client
from app.services.qloo.tastecare import recommend_meals, MEDICATION_DISCLAIMER, DEFAULT_AGE_SIGNAL

router = APIRouter(prefix="/tastecare", tags=["tastecare"])


class SeniorProfile(BaseModel):
    cultural_likes: list[str] = Field(
        default_factory=list,
        description="Cultural preferences: cuisines / artists / films etc., used as Qloo taste anchors",
    )
    cuisine_tags: list[str] = Field(
        default_factory=list,
        description="Optional: Qloo cuisine tag IDs (e.g. urn:tag:genre:...)",
    )
    location: str | None = Field(default=None, description="Region / city, e.g. 'New York'")
    constraints: dict[str, Any] = Field(
        default_factory=dict,
        description="Health constraints: { low_sugar, low_sodium, soft_chewable, medications }",
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
    data_source: str = "preview"


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
        data_source=result.get("data_source") or ("live" if client.enabled else "preview"),
    )


# ===== Multi-Domain Itinerary =====

class ItineraryRequest(BaseModel):
    cultural_likes: list[str] = Field(..., min_length=1)
    location: str | None = Field(default=None)
    constraints: dict[str, Any] = Field(default_factory=dict)
    take: int = Field(default=6, ge=1, le=20)


class ItineraryItem(BaseModel):
    domain: str
    entity_id: str
    name: str
    fit: float
    popularity: float | None = None
    type: str


class ItineraryResponse(BaseModel):
    itinerary: list[ItineraryItem] = Field(default_factory=list)
    anchor_count: int = 0
    data_source: str = "preview"


@router.post("/itinerary", response_model=ItineraryResponse)
async def multi_domain_itinerary(payload: ItineraryRequest):
    from app.services.qloo.tastecare import build_multi_domain_itinerary
    client = _ensure_client()
    result = await build_multi_domain_itinerary(client, payload.cultural_likes, payload.location, payload.constraints, take=payload.take)
    items = [ItineraryItem(**item) for item in result.get("itinerary", [])]
    return ItineraryResponse(itinerary=items, anchor_count=result.get("anchor_count", 0), data_source=result.get("data_source", "preview"))


@router.get("/liked-anchors")
async def get_liked_anchors(session_id: str = Query(default="default", description="Session key for the user's persistent taste-feedback store.")):
    from app.services.qloo.feedback import get_feedback_store

    store = get_feedback_store(session_id)
    liked = store.get_liked_taste_names()
    disliked = store.get_disliked_taste_names()
    return {"liked": sorted(liked.keys()), "disliked": sorted(disliked.keys())}