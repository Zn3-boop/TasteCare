from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.qloo.client import get_qloo_client
from app.services.qloo.taste import (
    search_cultural_entities,
    get_taste_based_recommendations,
    get_cross_domain_discovery,
    get_cross_domain_bridge_graph,
    get_taste_similarity_score,
    build_cultural_context_for_llm,
)
from app.services.qloo.entities import (
    resolve_entity,
    resolve_entities_batch,
    get_entity_details,
    get_entity_taste_profile,
    score_cultural_fit,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/qloo", tags=["qloo"])


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query for cultural entities")
    domain: str | None = Field(default=None, description="Domain filter: music, film, dining, fashion, travel, podcast, book")
    limit: int = Field(default=10, ge=1, le=50)


class SearchResponse(BaseModel):
    results: list[dict[str, Any]] = Field(default_factory=list)
    source: str = "qloo"


class RecommendRequest(BaseModel):
    seed_entity_ids: list[str] = Field(..., min_length=1, description="Entity IDs to base recommendations on")
    target_domain: str | None = Field(default=None, description="Target domain for recommendations")
    limit: int = Field(default=10, ge=1, le=50)


class RecommendResponse(BaseModel):
    recommendations: list[dict[str, Any]] = Field(default_factory=list)
    source: str = "qloo"
    seed_count: int = 0
    target_domain: str | None = None


class CrossDomainRequest(BaseModel):
    seed_entity_ids: list[str] = Field(..., min_length=1)
    domains: list[str] | None = Field(default=None)
    per_domain_limit: int = Field(default=5, ge=1, le=20)


class CrossDomainResponse(BaseModel):
    results: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    source: str = "qloo"


class SimilarityRequest(BaseModel):
    entity_ids: list[str] = Field(..., min_length=1)
    target_type: str | None = Field(default=None)
    limit: int = Field(default=10, ge=1, le=50)


class SimilarityResponse(BaseModel):
    similar: list[dict[str, Any]] = Field(default_factory=list)
    source: str = "qloo"


class CulturalFitRequest(BaseModel):
    seed_names: list[str] = Field(..., min_length=1, description="Names of entities the user likes")
    candidate_names: list[str] = Field(..., min_length=1, description="Names of candidate entities to score")
    domain: str | None = Field(default=None)


class CulturalFitResponse(BaseModel):
    scores: list[dict[str, Any]] = Field(default_factory=list)
    source: str = "qloo"


class TasteProfileRequest(BaseModel):
    entity_ids: list[str] = Field(..., min_length=1)


class TasteProfileResponse(BaseModel):
    profile: dict[str, Any] = Field(default_factory=dict)
    source: str = "qloo"


class LLMContextRequest(BaseModel):
    user_likes: list[str] = Field(..., min_length=1, description="Names of things the user likes")
    target_domain: str | None = Field(default=None)
    limit: int = Field(default=8, ge=1, le=20)


class LLMContextResponse(BaseModel):
    context: str = ""
    source: str = "qloo"


class QlooStatusResponse(BaseModel):
    enabled: bool
    base_url: str
    api_key_set: bool


def _ensure_client():
    client = get_qloo_client()
    if not client.enabled:
        raise HTTPException(status_code=503, detail="Qloo API is not configured. Set QLOO_API_KEY environment variable.")
    return client


@router.get("/status", response_model=QlooStatusResponse)
async def qloo_status():
    client = get_qloo_client()
    return QlooStatusResponse(
        enabled=client.enabled,
        base_url=client.config.base_url,
        api_key_set=bool(client.config.api_key),
    )


@router.post("/search", response_model=SearchResponse)
async def search_entities(payload: SearchRequest):
    client = _ensure_client()
    results = await search_cultural_entities(client, payload.query, domain=payload.domain, limit=payload.limit)
    return SearchResponse(results=results)


@router.post("/recommend", response_model=RecommendResponse)
async def recommend(payload: RecommendRequest):
    client = _ensure_client()
    result = await get_taste_based_recommendations(
        client, payload.seed_entity_ids, target_domain=payload.target_domain, limit=payload.limit,
    )
    return RecommendResponse(
        recommendations=result.get("recommendations", []),
        seed_count=result.get("seed_count", 0),
        target_domain=result.get("target_domain"),
    )


@router.post("/cross-domain", response_model=CrossDomainResponse)
async def cross_domain(payload: CrossDomainRequest):
    client = _ensure_client()
    results = await get_cross_domain_discovery(
        client, payload.seed_entity_ids, domains=payload.domains, per_domain_limit=payload.per_domain_limit,
    )
    return CrossDomainResponse(results=results)


class BridgeGraphRequest(BaseModel):
    seed_entity_ids: list[str] = Field(default_factory=list)
    center_label: str = Field(default="", description="Label of the central taste anchor")
    domains: list[str] | None = Field(default=None)
    per_domain_limit: int = Field(default=5, ge=1, le=20)


class BridgeGraphResponse(BaseModel):
    center: str
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)
    data_source: str = "preview"


@router.post("/bridge-graph", response_model=BridgeGraphResponse)
async def bridge_graph(payload: BridgeGraphRequest):
    """Return an explicit cross-domain graph JSON ({center, nodes, edges, why}).

    Unlike /cross-domain, this endpoint works even without QLOO_API_KEY: when the
    client is disabled it returns the clearly-labelled demo preview pool
    (data_source="preview") so the Taste Bridge constellation is always explorable.
    """
    client = get_qloo_client()
    center = payload.center_label or (payload.seed_entity_ids[0] if payload.seed_entity_ids else "Frank Sinatra")
    result = await get_cross_domain_bridge_graph(
        client,
        payload.seed_entity_ids,
        center_label=center,
        domains=payload.domains,
        per_domain_limit=payload.per_domain_limit,
    )
    return BridgeGraphResponse(**result)


@router.post("/similarity", response_model=SimilarityResponse)
async def similarity(payload: SimilarityRequest):
    client = _ensure_client()
    result = await get_taste_similarity_score(
        client, payload.entity_ids, target_type=payload.target_type, limit=payload.limit,
    )
    return SimilarityResponse(similar=result.get("similar", []))


@router.post("/cultural-fit", response_model=CulturalFitResponse)
async def cultural_fit(payload: CulturalFitRequest):
    client = _ensure_client()
    result = await score_cultural_fit(
        client, payload.seed_names, payload.candidate_names, domain=payload.domain,
    )
    return CulturalFitResponse(scores=result.get("scores", []))


@router.post("/taste-profile", response_model=TasteProfileResponse)
async def taste_profile(payload: TasteProfileRequest):
    client = _ensure_client()
    result = await get_entity_taste_profile(client, payload.entity_ids)
    return TasteProfileResponse(profile=result.get("profile", {}))


@router.post("/llm-context", response_model=LLMContextResponse)
async def llm_context(payload: LLMContextRequest):
    client = _ensure_client()
    context = await build_cultural_context_for_llm(
        client, payload.user_likes, target_domain=payload.target_domain, limit=payload.limit,
    )
    return LLMContextResponse(context=context)


@router.get("/entity/{entity_id}")
async def get_entity(entity_id: str):
    client = _ensure_client()
    result = await get_entity_details(client, entity_id)
    return result