from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class QlooConfig:
    api_key: str
    base_url: str
    timeout_seconds: float
    max_retries: int

    @classmethod
    def from_env(cls) -> QlooConfig:
        api_key = os.getenv("QLOO_API_KEY", "")
        # Hackathon keys are only valid against the hackathon base URL.
        # Override via QLOO_BASE_URL if you have production/staging access.
        base_url = os.getenv("QLOO_BASE_URL", "https://hackathon.api.qloo.com")
        timeout = float(os.getenv("QLOO_TIMEOUT_SECONDS", "30"))
        retries = int(os.getenv("QLOO_MAX_RETRIES", "3"))
        return cls(
            api_key=api_key,
            base_url=base_url.rstrip("/"),
            timeout_seconds=timeout,
            max_retries=retries,
        )

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)