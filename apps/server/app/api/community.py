"""Community API — find and connect with people who share your cultural taste
and health needs. Runs entirely on Qloo's cloud API (search / insights) — no
LLM key and no local models required.

Connections use mutual opt-in: a request is created as ``pending`` and only
becomes ``connected`` after the other party accepts (privacy by design).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.community import (
    DEMO_PEERS,
    accept_connection,
    list_connections,
    match_peers,
    request_connection,
    semantic_match_peers,
)
from app.services.qloo.client import get_qloo_client

router = APIRouter(prefix="/community", tags=["community"])


class MatchRequest(BaseModel):
    cultural_likes: list[str] = Field(..., min_length=1, description="Cultural anchors (artists, films, cuisines…).")
    location: str | None = Field(default=None, description="City, e.g. 'New York' (affects affinity bonus).")
    constraints: dict[str, Any] = Field(default_factory=dict, description="Health constraints: low_sodium / low_sugar / soft_chewable / medications.")
    limit: int = Field(default=5, ge=1, le=10)
    semantic: bool = Field(default=False, description="Use the local numpy-cosine semantic matcher (sentence-transformers + all-MiniLM-L6-v2, No FAISS) instead of Qloo entity overlap.")


class MatchResponse(BaseModel):
    matches: list[dict[str, Any]] = Field(default_factory=list)
    user_likes_resolved: list[dict[str, Any]] = Field(default_factory=list)
    data_source: str = "preview"


class ConnectRequest(BaseModel):
    peer_id: str = Field(..., min_length=1)


class ConnectResponse(BaseModel):
    ok: bool
    peer_id: str
    status: str = ""
    message: str = ""
    error: str | None = None


@router.post("/match", response_model=MatchResponse)
async def community_match(payload: MatchRequest):
    """Find demo peers with overlapping cultural anchors + health constraints.

    When a Qloo key is configured the anchors are resolved against the real
    Qloo taste graph (``data_source: live``); otherwise the matching uses the
    clearly-labelled demo pool (``data_source: preview``).

    ``semantic=true`` routes to the local numpy-cosine matcher
    (sentence-transformers + all-MiniLM-L6-v2, NO FAISS and no Qloo key
    needed) — the lightweight demo vector-search path documented in the
    README scaling section.
    """
    client = get_qloo_client()
    if payload.semantic:
        result = await semantic_match_peers(
            payload.cultural_likes,
            user_constraints=payload.constraints,
            location=payload.location,
            limit=payload.limit,
        )
    else:
        result = await match_peers(
            client,
            payload.cultural_likes,
            user_constraints=payload.constraints,
            location=payload.location,
            limit=payload.limit,
        )
    return MatchResponse(
        matches=result["matches"],
        user_likes_resolved=result["user_likes_resolved"],
        data_source=result["data_source"],
    )


@router.post("/connect", response_model=ConnectResponse)
async def community_connect(payload: ConnectRequest):
    """Send a PENDING connection request to a matched peer."""
    result = request_connection(payload.peer_id)
    if not result.get("ok"):
        return ConnectResponse(ok=False, peer_id=payload.peer_id, error=result.get("error"))
    return ConnectResponse(
        ok=True,
        peer_id=payload.peer_id,
        status=result.get("status", "pending"),
        message=result.get("message", ""),
    )


@router.post("/accept", response_model=ConnectResponse)
async def community_accept(payload: ConnectRequest):
    """The other party accepts — this is the mutual-opt-in step."""
    result = accept_connection(payload.peer_id)
    if not result.get("ok"):
        return ConnectResponse(ok=False, peer_id=payload.peer_id, error=result.get("error"))
    return ConnectResponse(
        ok=True,
        peer_id=payload.peer_id,
        status=result.get("status", "pending"),
        message="Accepted. You are now connected to this person.",
    )


@router.get("/connections")
async def community_connections():
    return {"connections": list_connections()}


@router.get("/status")
async def community_status():
    client = get_qloo_client()
    return {
        "enabled": client.enabled,
        "peer_pool_size": len(DEMO_PEERS),
        "note": "Demo peer pool is simulated and clearly labelled; matching math runs on live Qloo entities when a key is configured.",
    }