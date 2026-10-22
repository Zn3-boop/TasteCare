from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memory", tags=["memory"])


class LikedEntity(BaseModel):
    entity_id: str = Field(..., description="Qloo entity UUID")
    name: str = Field(..., description="Display name")
    domain: str = Field("", description="Domain label")
    added_at: str = Field("", description="ISO-8601 timestamp")


class MemoryState(BaseModel):
    liked: list[LikedEntity] = Field(default_factory=list)
    disliked: list[LikedEntity] = Field(default_factory=list)
    data_source: str = "preview"


_liked: list[dict[str, str]] = []
_disliked: list[dict[str, str]] = []
class AddRequest(BaseModel):
    entity_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    domain: str = Field("", description="e.g. music, film, dining, fashion, travel")
    thumb: str = Field("up", description="up or down")


class AddResponse(BaseModel):
    ok: bool
    entity_id: str
    name: str
    data_source: str


class ClearResponse(BaseModel):
    ok: bool


@router.get("/state", response_model=MemoryState)
async def get_memory_state() -> MemoryState:
    return MemoryState(
        liked=[LikedEntity(**e) for e in _liked],
        disliked=[LikedEntity(**e) for e in _disliked],
        data_source="preview",
    )


@router.post("/add", response_model=AddResponse)
async def add_to_memory(payload: AddRequest) -> AddResponse:
    global _liked, _disliked
    record = {"entity_id": payload.entity_id, "name": payload.name, "domain": payload.domain, "added_at": ""}
    if payload.thumb == "up":
        _liked = [e for e in _liked if e["entity_id"] != payload.entity_id]
        _liked.insert(0, record)
    else:
        _disliked = [e for e in _disliked if e["entity_id"] != payload.entity_id]
        _disliked.insert(0, record)
    logger.info("[Memory] added: %s", payload.name)
    return AddResponse(ok=True, entity_id=payload.entity_id, name=payload.name, data_source="preview")


@router.post("/clear", response_model=ClearResponse)
async def clear_memory() -> ClearResponse:
    global _liked, _disliked
    _liked.clear()
    _disliked.clear()
    return ClearResponse(ok=True)