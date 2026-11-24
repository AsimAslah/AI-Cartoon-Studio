from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Callable

from app.services.video_generation.contracts import VideoQuotaState, VideoQuotaStatus


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _http_status(exc: Exception) -> int | None:
    response = getattr(exc, "response", None)
    value = getattr(response, "status_code", None) if response is not None else None
    if value is None:
        value = getattr(exc, "status_code", None)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


class HuggingFaceQuotaService:
    """Read-only, explicitly authenticated ZeroGPU quota cache."""

    def __init__(
        self,
        token: str | None,
        *,
        api_factory: Callable[[str], Any] | None = None,
        clock: Callable[[], datetime] = utc_now,
    ):
        self._token = token
        self._api_factory = api_factory
        self._clock = clock
        self._lock = threading.RLock()
        self._last_successful_refresh_at: datetime | None = None
        self._status = self._initial_status()

    def _initial_status(self) -> VideoQuotaStatus:
        if not self._token:
            return VideoQuotaStatus(
                state=VideoQuotaState.AUTHENTICATION_REQUIRED,
                authentication_status="missing",
                message="Quota is unavailable until AI_CARTOON_HF_TOKEN is configured explicitly.",
            )
        return VideoQuotaStatus(
            state=VideoQuotaState.UNKNOWN,
            authentication_status="configured_not_checked",
            message="Quota has not been refreshed. Refreshing quota is read-only and never starts inference.",
        )

    def _build_api(self):
        if self._api_factory is not None:
            return self._api_factory(self._token)  # type: ignore[arg-type]
        from huggingface_hub import HfApi

        return HfApi(token=self._token)

    def current(self) -> VideoQuotaStatus:
        with self._lock:
            return self._status.model_copy(deep=True)

    def refresh(self) -> VideoQuotaStatus:
        if not self._token:
            with self._lock:
                self._status = self._initial_status()
                return self._status.model_copy(deep=True)
        try:
            quota = self._build_api().get_zero_gpu_quota(token=self._token)
            total = max(0.0, float(quota.base))
            remaining = max(0.0, float(quota.remaining))
            refreshed_at = self._clock()
            self._last_successful_refresh_at = refreshed_at
            state = VideoQuotaState.EXHAUSTED if remaining <= 0 else VideoQuotaState.AVAILABLE
            message = (
                "ZeroGPU quota is exhausted. Wait for the reset or review account credit settings."
                if state == VideoQuotaState.EXHAUSTED
                else "ZeroGPU quota is available, but availability does not guarantee that a specific reservation will be accepted."
            )
            status = VideoQuotaStatus(
                state=state,
                authentication_status="authenticated",
                total_gpu_seconds=total,
                remaining_gpu_seconds=remaining,
                resets_at=quota.resets_at,
                last_successful_refresh_at=refreshed_at,
                message=message,
            )
        except Exception as exc:
            status_code = _http_status(exc)
            if status_code == 401:
                status = VideoQuotaStatus(
                    state=VideoQuotaState.AUTHENTICATION_REQUIRED,
                    authentication_status="invalid",
                    last_successful_refresh_at=self._last_successful_refresh_at,
                    message="Hugging Face rejected the configured token while reading ZeroGPU quota.",
                )
            elif status_code == 403:
                status = VideoQuotaStatus(
                    state=VideoQuotaState.PERMISSION_DENIED,
                    authentication_status="permission_denied",
                    last_successful_refresh_at=self._last_successful_refresh_at,
                    message=(
                        "The token cannot read ZeroGPU quota. A fine-grained token needs Billing > Read billing "
                        "usage and payment method status; generation permissions were not changed."
                    ),
                )
            else:
                status = VideoQuotaStatus(
                    state=VideoQuotaState.UNAVAILABLE,
                    authentication_status="unavailable",
                    last_successful_refresh_at=self._last_successful_refresh_at,
                    message="ZeroGPU quota could not be refreshed. No inference was started.",
                )
        with self._lock:
            self._status = status
            return status.model_copy(deep=True)
