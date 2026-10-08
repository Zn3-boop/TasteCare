"""Deep tests for the Qloo response cache (cache.py).

The cache now backs every successful GET in QlooClient._request, so these tests
pin the two properties that actually matter at runtime:

  * TTL expiry — a stale entry must never be served after `ttl` seconds.
  * LRU-ish eviction — when the max-entry bound is hit, the OLDEST entry is
    dropped so the cache cannot grow unbounded.

Also covered: deterministic key building (same kwargs -> same key, regardless of
kwarg order; different method/path/kwargs -> different key), clear_cache, and a
client-level integration test proving a repeated identical search issues exactly
one HTTP request.

Network-free: no Qloo HTTP call is made in this file.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.services.qloo.cache import (
    DEFAULT_TTL,
    MAX_ENTRIES,
    _make_key,
    clear_cache,
    get_cached,
    set_cached,
)
from app.services.qloo.client import QlooClient
from app.services.qloo.config import QlooConfig


@pytest.fixture(autouse=True)
def _fresh_cache():
    clear_cache()
    yield
    clear_cache()


# ═══════════════════════════════════════════════════════════════════════════
# 1. Key building — determinism and discrimination
# ═══════════════════════════════════════════════════════════════════════════

class TestKeyBuilding:
    def test_same_kwargs_same_key(self):
        a = _make_key("GET", "/search", base_url="https://x", params={"query": "Jazz", "take": 5})
        b = _make_key("GET", "/search", base_url="https://x", params={"query": "Jazz", "take": 5})
        assert a == b
        assert len(a) == 32  # md5 hexdigest

    def test_kwarg_order_does_not_change_key(self):
        a = _make_key("GET", "/search", a=1, b=2)
        b = _make_key("GET", "/search", b=2, a=1)
        assert a == b

    def test_different_method_changes_key(self):
        a = _make_key("GET", "/search", params={"query": "Jazz"})
        b = _make_key("POST", "/search", params={"query": "Jazz"})
        assert a != b

    def test_different_path_changes_key(self):
        a = _make_key("GET", "/search", params={"query": "Jazz"})
        b = _make_key("GET", "/v2/tags", params={"query": "Jazz"})
        assert a != b

    def test_different_params_change_key(self):
        a = _make_key("GET", "/search", params={"query": "Jazz"})
        b = _make_key("GET", "/search", params={"query": "Blues"})
        assert a != b

    def test_different_base_url_changes_key(self):
        # Critical: two Qloo environments must never share cache entries.
        a = _make_key("GET", "/search", base_url="https://hackathon.api.qloo.com", params={"query": "Jazz"})
        b = _make_key("GET", "/search", base_url="https://staging.api.qloo.com", params={"query": "Jazz"})
        assert a != b


# ═══════════════════════════════════════════════════════════════════════════
# 2. get/set semantics — miss, hit, overwrite, clear
# ═══════════════════════════════════════════════════════════════════════════

class TestGetSet:
    def test_get_miss_returns_none(self):
        assert get_cached("GET", "/search", params={"query": "Jazz"}) is None

    def test_set_then_get_roundtrip(self):
        set_cached("GET", "/search", {"results": ["x"]}, params={"query": "Jazz"})
        assert get_cached("GET", "/search", params={"query": "Jazz"}) == {"results": ["x"]}

    def test_set_overwrites_existing_value(self):
        set_cached("GET", "/search", "v1", params={"query": "Jazz"})
        set_cached("GET", "/search", "v2", params={"query": "Jazz"})
        assert get_cached("GET", "/search", params={"query": "Jazz"}) == "v2"

    def test_clear_cache_empties_entries(self):
        set_cached("GET", "/search", "v", params={"query": "Jazz"})
        clear_cache()
        assert get_cached("GET", "/search", params={"query": "Jazz"}) is None
# ═══════════════════════════════════════════════════════════════════════════
# 3. TTL expiry — controlled clock
# ═══════════════════════════════════════════════════════════════════════════

class TestTTL:
    def _install_clock(self, monkeypatch, start=1_000_000.0):
        state = {"now": start}

        def _fake_time():
            return state["now"]

        monkeypatch.setattr("app.services.qloo.cache.time.time", _fake_time)
        return state

    def test_serves_within_ttl(self, monkeypatch):
        clock = self._install_clock(monkeypatch)
        set_cached("GET", "/search", "v", params={"query": "Jazz"})
        clock["now"] += DEFAULT_TTL - 1
        assert get_cached("GET", "/search", params={"query": "Jazz"}) == "v"

    def test_expires_at_ttl_boundary(self, monkeypatch):
        clock = self._install_clock(monkeypatch)
        set_cached("GET", "/search", "v", params={"query": "Jazz"})
        clock["now"] += DEFAULT_TTL  # == ttl passes (strict >)
        assert get_cached("GET", "/search", params={"query": "Jazz"}) == "v"
        clock["now"] += 0.001
        assert get_cached("GET", "/search", params={"query": "Jazz"}) is None

    def test_expired_entry_removed_from_cache(self, monkeypatch):
        clock = self._install_clock(monkeypatch)
        set_cached("GET", "/search", "v", params={"query": "Jazz"})
        clock["now"] += DEFAULT_TTL + 10
        assert get_cached("GET", "/search", params={"query": "Jazz"}) is None
        # Miss again -> the expired entry must already be deleted (no stale hit).
        assert get_cached("GET", "/search", params={"query": "Jazz"}) is None

    def test_custom_ttl_respected(self, monkeypatch):
        clock = self._install_clock(monkeypatch)
        set_cached("GET", "/search", "v", params={"query": "Jazz"})
        clock["now"] += 60
        # Default TTL (300s) still valid, custom short TTL expired:
        assert get_cached("GET", "/search", params={"query": "Jazz"}) == "v"
        assert get_cached("GET", "/search", ttl=30, params={"query": "Jazz"}) is None

    def test_independent_entries_expire_independently(self, monkeypatch):
        clock = self._install_clock(monkeypatch)
        set_cached("GET", "/search", "a", params={"query": "Jazz"})
        clock["now"] += 100
        set_cached("GET", "/search", "b", params={"query": "Blues"})
        clock["now"] += 250  # total 350s: Jazz (ts=0) expired, Blues (ts=100) alive
        assert get_cached("GET", "/search", params={"query": "Jazz"}) is None
        assert get_cached("GET", "/search", params={"query": "Blues"}) == "b"


# ═══════════════════════════════════════════════════════════════════════════
# 4. Max-entry eviction — bounded memory
# ═══════════════════════════════════════════════════════════════════════════

class TestEviction:
    def test_never_exceeds_max_entries(self, monkeypatch):
        clock = {"now": 1000.0}
        monkeypatch.setattr("app.services.qloo.cache.time.time", lambda: clock["now"])
        for i in range(MAX_ENTRIES + 50):
            clock["now"] += 1
            set_cached("GET", "/search", i, params={"query": f"q{i}"})
        # Cache must stay bounded even after inserting well past the cap.
        from app.services.qloo import cache as _c

        assert len(_c._cache) <= MAX_ENTRIES

    def test_oldest_entry_evicted_first(self, monkeypatch):
        clock = {"now": 1000.0}
        monkeypatch.setattr("app.services.qloo.cache.time.time", lambda: clock["now"])
        for i in range(MAX_ENTRIES):
            clock["now"] += 1
            set_cached("GET", "/search", i, params={"query": f"q{i}"})
        assert get_cached("GET", "/search", params={"query": f"q{MAX_ENTRIES-1}"}) == MAX_ENTRIES - 1
        # One more insert evicts the oldest (q0).
        clock["now"] += 1
        set_cached("GET", "/search", "new", params={"query": "fresh"})
        assert get_cached("GET", "/search", params={"query": "q0"}) is None
        assert get_cached("GET", "/search", params={"query": "q1"}) == 1

    def test_eviction_preserves_most_recently_stored(self, monkeypatch):
        clock = {"now": 1000.0}
        monkeypatch.setattr("app.services.qloo.cache.time.time", lambda: clock["now"])
        for i in range(MAX_ENTRIES):
            clock["now"] += 1
            set_cached("GET", "/search", i, params={"query": f"q{i}"})
        # Refresh q0's timestamp by re-storing it — it must now survive eviction.
        clock["now"] += 1
        set_cached("GET", "/search", "refreshed", params={"query": "q0"})
        clock["now"] += 1
        set_cached("GET", "/search", "new", params={"query": "fresh"})
        assert get_cached("GET", "/search", params={"query": "q0"}) == "refreshed"
        # The genuinely oldest entry (q1) is the one evicted.
        assert get_cached("GET", "/search", params={"query": "q1"}) is None
# ═══════════════════════════════════════════════════════════════════════════
# 5. Client integration — repeated identical search issues exactly one HTTP call
# ═══════════════════════════════════════════════════════════════════════════

class _FakeResponse:
    def __init__(self, payload: dict[str, Any], status: int = 200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import httpx

            req = httpx.Request("GET", "http://test")
            raise httpx.HTTPStatusError(
                "error", request=req, response=httpx.Response(self.status_code, request=req)
            )

    def json(self) -> dict[str, Any]:
        return self._payload


class _CountingFakeHTTP:
    """Minimal AsyncClient stand-in that counts request() invocations."""

    def __init__(self, payload: dict[str, Any]):
        self._payload = payload
        self.calls = 0
        self.is_closed = False

    async def request(self, method: str, url: str, **kwargs: Any) -> _FakeResponse:
        self.calls += 1
        return _FakeResponse(self._payload)

    async def aclose(self) -> None:
        self.is_closed = True


class TestClientCacheIntegration:
    @pytest.mark.asyncio
    async def test_identical_search_cached_after_first_call(self):
        client = QlooClient(config=QlooConfig(api_key="k", base_url="https://hackathon.api.qloo.com", timeout_seconds=5, max_retries=1))
        fake = _CountingFakeHTTP({"results": {"entities": [{"name": "Jazz Club", "entity_id": "e1"}]}})
        with patch.object(client, "_get_http", new_callable=AsyncMock, return_value=fake):
            r1 = await client.search("Jazz")
            r2 = await client.search("Jazz")
        assert r1 == r2
        assert fake.calls == 1  # second call served from cache, no HTTP

    @pytest.mark.asyncio
    async def test_different_params_are_not_cached_together(self):
        client = QlooClient(config=QlooConfig(api_key="k", base_url="https://hackathon.api.qloo.com", timeout_seconds=5, max_retries=1))
        fake = _CountingFakeHTTP({"results": {"entities": []}})
        with patch.object(client, "_get_http", new_callable=AsyncMock, return_value=fake):
            await client.search("Jazz")
            await client.search("Blues")
        assert fake.calls == 2  # different query -> different cache key

    @pytest.mark.asyncio
    async def test_error_payload_is_never_cached(self):
        client = QlooClient(config=QlooConfig(api_key="k", base_url="https://hackathon.api.qloo.com", timeout_seconds=5, max_retries=1))
        fake = _CountingFakeHTTP({"error": "bad_request", "detail": "x"})
        with patch.object(client, "_get_http", new_callable=AsyncMock, return_value=fake):
            r1 = await client.search("Jazz")
            r2 = await client.search("Jazz")
        assert r1["error"] == "bad_request"
        assert fake.calls == 2  # error dicts must not be cached

    @pytest.mark.asyncio
    async def test_clear_cache_forces_refetch(self):
        client = QlooClient(config=QlooConfig(api_key="k", base_url="https://hackathon.api.qloo.com", timeout_seconds=5, max_retries=1))
        fake = _CountingFakeHTTP({"results": {"entities": []}})
        with patch.object(client, "_get_http", new_callable=AsyncMock, return_value=fake):
            await client.search("Jazz")
            clear_cache()
            await client.search("Jazz")
        assert fake.calls == 2
