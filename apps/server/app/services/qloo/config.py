from __future__ import annotations

from dataclasses import dataclass

from app.core.config import get_settings


@dataclass(frozen=True)
class QlooConfig:
    api_key: str
    base_url: str
    timeout_seconds: float
    max_retries: int

    @classmethod
    def from_env(cls) -> QlooConfig:
        # 部署关键配置统一走 app.core.config（pydantic-settings）；不缓存，
        # 以保证测试里 patch.dict("os.environ", ...) 对 from_env() 实时生效。
        settings = get_settings()
        return cls(
            api_key=settings.qloo_api_key,
            # Hackathon keys are only valid against the hackathon base URL.
            # Override via QLOO_BASE_URL if you have production/staging access.
            base_url=settings.qloo_base_url.rstrip("/"),
            timeout_seconds=settings.qloo_timeout_seconds,
            max_retries=settings.qloo_max_retries,
        )

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)