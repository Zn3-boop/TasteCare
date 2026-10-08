from __future__ import annotations

import hashlib
import time
from typing import Any

_cache: dict[str, tuple[float, Any]] = {}

DEFAULT_TTL = 300
MAX_ENTRIES = 256


def _make_key(method: str, path: str, **kwargs: Any) -> str:
    raw = f"{method}:{path}:{sorted(kwargs.items())}"
    return hashlib.md5(raw.encode()).hexdigest()


def get_cached(method: str, path: str, ttl: float = DEFAULT_TTL, **kwargs: Any) -> Any | None:
    key = _make_key(method, path, **kwargs)
    entry = _cache.get(key)
    if entry is None:
        return None
    ts, value = entry
    if time.time() - ts > ttl:
        del _cache[key]
        return None
    return value


def set_cached(method: str, path: str, value: Any, **kwargs: Any) -> None:
    global _cache
    if len(_cache) >= MAX_ENTRIES:
        oldest_key = min(_cache, key=lambda k: _cache[k][0])
        del _cache[oldest_key]
    key = _make_key(method, path, **kwargs)
    _cache[key] = (time.time(), value)


def clear_cache() -> None:
    _cache.clear()