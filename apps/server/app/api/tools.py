from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("/")
async def list_tools():
    return {"tools": [], "note": "Tool registry cleaned — use /qloo/* and /tastecare/* endpoints"}