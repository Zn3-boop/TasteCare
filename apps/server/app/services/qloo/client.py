from __future__ import annotations

import logging
from typing import Any

import httpx

from app.services.qloo.cache import get_cached, set_cached
from app.services.qloo.config import QlooConfig

logger = logging.getLogger(__name__)

_qloo_client: QlooClient | None = None


class QlooClient:
    def __init__(self, config: QlooConfig | None = None) -> None:
        self._config = config or QlooConfig.from_env()
        self._http: httpx.AsyncClient | None = None

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    @property
    def config(self) -> QlooConfig:
        return self._config

    async def _get_http(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                base_url=self._config.base_url,
                headers={
                    "X-Api-Key": self._config.api_key,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=httpx.Timeout(self._config.timeout_seconds, connect=10.0),
            )
        return self._http

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
            self._http = None

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        # Cache only successful GET query calls, keyed by (method, path,
        # base_url, params). The key is scoped to base_url so different Qloo
        # environments (hackathon vs staging) never share stale responses.
        cacheable = method.upper() == "GET" and bool(kwargs.get("params"))
        if cacheable:
            cached = get_cached(
                method.upper(),
                path,
                base_url=self._config.base_url,
                params=kwargs["params"],
            )
            if cached is not None:
                logger.debug("Qloo cache hit: %s %s", method, path)
                return cached

        http = await self._get_http()
        last_exc: Exception | None = None
        for attempt in range(self._config.max_retries):
            try:
                resp = await http.request(method, path, **kwargs)
                resp.raise_for_status()
                payload = resp.json()
                if cacheable and isinstance(payload, dict) and "error" not in payload:
                    set_cached(
                        method.upper(),
                        path,
                        payload,
                        base_url=self._config.base_url,
                        params=kwargs["params"],
                    )
                return payload
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                logger.error(f"Qloo API error {status}: {e.response.text[:500]}")
                if status == 401 or status == 403:
                    return {"error": "auth_failed", "detail": f"status={status}"}
                if status == 400:
                    return {"error": "bad_request", "detail": e.response.text[:500]}
                if status == 404:
                    return {"error": "not_found", "detail": e.response.text[:300]}
                if status == 429:
                    logger.warning(f"Qloo rate limited (attempt {attempt+1})")
                    last_exc = e
                else:
                    last_exc = e
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                logger.warning(f"Qloo API timeout/connect (attempt {attempt+1}): {e}")
                last_exc = e
            except Exception as e:
                logger.error(f"Qloo API unexpected error: {e}")
                last_exc = e
        return {"error": "request_failed", "detail": str(last_exc)}

    # ================= Search Entities (Lookup) =================
    # GET /search?query=...&types=urn:entity:movie&take=...
    async def search(
        self,
        query: str,
        entity_types: list[str] | None = None,
        take: int = 10,
        **extra: Any,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"query": query, "take": take}
        if entity_types:
            params["types"] = ",".join(entity_types)
        for k, v in extra.items():
            if v is not None:
                params[k] = v
        return await self._request("GET", "/search", params=params)

    # ================= Search Tags (Lookup) =================
    # GET /v2/tags?query=...&take=...
    async def search_tags(self, query: str, take: int = 10, **extra: Any) -> dict[str, Any]:
        params: dict[str, Any] = {"query": query, "take": take}
        for k, v in extra.items():
            if v is not None:
                params[k] = v
        return await self._request("GET", "/v2/tags", params=params)

    # ================= Insights (core recommendation engine) =================
    # GET /v2/insights?filter.type=urn:entity:movie&signal.interests.entities=...
    async def insights(
        self,
        filter_type: str,
        signal_entities: list[str] | None = None,
        signal_tags: list[str] | None = None,
        filter_tags: list[str] | None = None,
        results_entities: list[str] | None = None,
        exclude_entities: list[str] | None = None,
        demographics_age: str | None = None,
        demographics_gender: str | None = None,
        demographics_audiences: list[str] | None = None,
        location_query: str | None = None,
        filters: dict[str, Any] | None = None,
        take: int = 20,
        **extra: Any,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"filter.type": filter_type, "take": take}
        if signal_entities:
            params["signal.interests.entities"] = ",".join(signal_entities)
        if signal_tags:
            params["signal.interests.tags"] = ",".join(signal_tags)
        if filter_tags:
            params["filter.tags"] = ",".join(filter_tags)
        if results_entities:
            params["filter.results.entities"] = ",".join(results_entities)
        if exclude_entities:
            params["filter.exclude.entities"] = ",".join(exclude_entities)
        if demographics_age:
            params["signal.demographics.age"] = demographics_age
        if demographics_gender:
            params["signal.demographics.gender"] = demographics_gender
        if demographics_audiences:
            params["signal.demographics.audiences"] = ",".join(demographics_audiences)
        if location_query:
            params["filter.location.query"] = location_query
        if filters:
            for k, v in filters.items():
                if v is not None:
                    params[k] = v
        for k, v in extra.items():
            if v is not None:
                params[k] = v
        return await self._request("GET", "/v2/insights", params=params)


def get_qloo_client() -> QlooClient:
    global _qloo_client
    if _qloo_client is None:
        _qloo_client = QlooClient()
    return _qloo_client
