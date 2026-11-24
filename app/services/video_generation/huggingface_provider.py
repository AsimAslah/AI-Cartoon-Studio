from __future__ import annotations

import importlib.util
import math
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from app.services.video_generation.contracts import (
    VideoGenerationRequest,
    VideoGenerationPreset,
    VideoGenerationSettings,
    VideoProviderCapabilities,
    VideoProviderResult,
    VideoProviderState,
)


class VideoProviderError(RuntimeError):
    error_code = "provider_failed"
    diagnostic_code = "hf_provider_failed"

    def __init__(self, message: str, *, diagnostic_code: str | None = None):
        super().__init__(message)
        if diagnostic_code:
            self.diagnostic_code = diagnostic_code


class VideoProviderNotConfiguredError(VideoProviderError):
    error_code = "provider_not_configured"


class VideoProviderAuthenticationError(VideoProviderError):
    error_code = "authentication_required"
    diagnostic_code = "hf_authentication_rejected"


class VideoProviderQuotaError(VideoProviderError):
    error_code = "zero_gpu_quota_insufficient"
    diagnostic_code = "hf_zero_gpu_quota_insufficient"


class VideoProviderQuotaExhaustedError(VideoProviderQuotaError):
    error_code = "zero_gpu_quota_exhausted"
    diagnostic_code = "hf_zero_gpu_quota_exhausted"


class VideoProviderReservationError(VideoProviderQuotaError):
    error_code = "zero_gpu_reservation_exceeds_remaining"
    diagnostic_code = "hf_zero_gpu_reservation_exceeds_remaining"


class VideoProviderRateLimitError(VideoProviderError):
    error_code = "rate_limited"
    diagnostic_code = "hf_http_429_rate_limit"


class VideoProviderQueueRejectedError(VideoProviderError):
    error_code = "queue_rejected"
    diagnostic_code = "hf_queue_capacity_rejected"


class VideoProviderTimeoutError(VideoProviderError):
    error_code = "provider_timeout"
    diagnostic_code = "hf_network_timeout"


class VideoProviderSchemaError(VideoProviderError):
    error_code = "provider_schema_changed"
    diagnostic_code = "hf_schema_incompatible"


class VideoProviderUnavailableError(VideoProviderError):
    error_code = "provider_unavailable"
    diagnostic_code = "hf_space_unavailable"


class VideoProviderInitializationError(VideoProviderError):
    error_code = "model_initialization_failed"
    diagnostic_code = "hf_model_initialization_failed"


class VideoProviderRequestValidationError(VideoProviderError):
    error_code = "provider_request_rejected"
    diagnostic_code = "hf_request_validation_failed"


class VideoProviderUnknownError(VideoProviderError):
    error_code = "provider_failure_unknown"
    diagnostic_code = "hf_unclassified_failure"


@dataclass(frozen=True)
class HuggingFaceVideoConfig:
    enabled: bool = False
    space_id: str = "Lightricks/LTX-2.5"
    api_name: str = "/run"
    token: str | None = None
    timeout_seconds: int = 900
    poll_interval_seconds: float = 1.0

    @classmethod
    def from_env(cls) -> "HuggingFaceVideoConfig":
        enabled = os.environ.get("AI_CARTOON_ENABLE_REMOTE_VIDEO", "").strip().lower() in {"1", "true", "yes"}
        space_id = os.environ.get("AI_CARTOON_HF_SPACE", "Lightricks/LTX-2.5").strip()
        api_name = os.environ.get("AI_CARTOON_HF_API_NAME", "/run").strip()
        token = os.environ.get("AI_CARTOON_HF_TOKEN") or None
        try:
            timeout = int(os.environ.get("AI_CARTOON_VIDEO_TIMEOUT_SECONDS", "900"))
        except ValueError as exc:
            raise VideoProviderNotConfiguredError(
                "AI_CARTOON_VIDEO_TIMEOUT_SECONDS must be an integer between 60 and 1800."
            ) from exc
        if space_id != "Lightricks/LTX-2.5":
            raise VideoProviderNotConfiguredError(
                "Only the reviewed Lightricks/LTX-2.5 Space is allowlisted in this milestone."
            )
        if api_name != "/run":
            raise VideoProviderNotConfiguredError("The reviewed LTX-2.5 API endpoint is /run.")
        if not 60 <= timeout <= 1_800:
            raise VideoProviderNotConfiguredError("Video timeout must be between 60 and 1800 seconds.")
        return cls(enabled=enabled, space_id=space_id, api_name=api_name, token=token, timeout_seconds=timeout)


class HuggingFaceLTXProvider:
    provider_id = "huggingface_ltx_2_5"
    name = "Hugging Face · LTX-2.5"
    model_id = "Lightricks/LTX-2.5-Diffusers"
    expected_parameters = {
        "prompt", "image_path", "height", "width", "duration_s", "seed",
        "decoder", "auto_len", "randomize_seed", "do_enhance",
    }
    low_resource_settings = VideoGenerationSettings(
        duration_seconds=1.0,
        width=1024,
        height=576,
        seed=42,
        decoder="conv",
        auto_length=False,
        randomize_seed=False,
        enhance_prompt=False,
    )

    def __init__(
        self,
        config: HuggingFaceVideoConfig,
        *,
        ffprobe_available: bool,
        client_factory: Callable[..., Any] | None = None,
        handle_file_factory: Callable[[str], Any] | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        configuration_error: str | None = None,
    ):
        self.config = config
        self.ffprobe_available = ffprobe_available
        self._client_factory = client_factory
        self._handle_file_factory = handle_file_factory
        self._sleep = sleep
        self._clock = clock
        self.configuration_error = configuration_error

    @staticmethod
    def dependency_available() -> bool:
        return importlib.util.find_spec("gradio_client") is not None

    def capabilities(self) -> VideoProviderCapabilities:
        dependency = self._client_factory is not None or self.dependency_available()
        if self.configuration_error:
            state = VideoProviderState.NOT_CONFIGURED
            note = self.configuration_error
        elif not self.config.enabled:
            state = VideoProviderState.NOT_CONFIGURED
            note = "Remote generation is disabled. Set AI_CARTOON_ENABLE_REMOTE_VIDEO=1 only after approving quota use."
        elif not dependency:
            state = VideoProviderState.DEPENDENCY_MISSING
            note = "Install the optional video dependency before enabling the provider."
        elif not self.config.token:
            state = VideoProviderState.AUTHENTICATION_REQUIRED
            note = (
                "Set AI_CARTOON_HF_TOKEN explicitly. The provider never falls back to a token "
                "cached by another Hugging Face application."
            )
        elif not self.ffprobe_available:
            state = VideoProviderState.DEPENDENCY_MISSING
            note = "ffprobe is required to verify resolution, frame rate, duration, and codec."
        else:
            state = VideoProviderState.AVAILABLE
            note = "Configured for the reviewed official LTX-2.5 /run endpoint. Each submission uploads media and consumes ZeroGPU quota."
        configured = state == VideoProviderState.AVAILABLE
        return VideoProviderCapabilities(
            provider_id=self.provider_id,
            name=self.name,
            model_id=self.model_id,
            state=state,
            configured=configured,
            credentials_required=True,
            credentials_configured=bool(self.config.token),
            may_incur_cost=True,
            space_id=self.config.space_id,
            api_name=self.config.api_name,
            supported_image_types=["image/png", "image/jpeg", "image/webp"],
            supported_durations=[1.0, 2.0, 3.0, 4.0, 5.0],
            resolution_presets={
                "landscape": (1024, 576),
                "portrait": (576, 1024),
                "square": (768, 768),
            },
            supported_decoders=["diffusion", "conv"],
            supports_seed=True,
            supports_prompt_enhancement=True,
            note=note,
        )

    @classmethod
    def low_resource_preset(cls) -> VideoGenerationPreset:
        return VideoGenerationPreset(
            settings=cls.low_resource_settings,
            expected_reservation_gpu_seconds=cls.estimated_quota_seconds(cls.low_resource_settings),
            reservation_verified_at="2026-11-24",
            reservation_note=(
                "Observed from the public LTX-2.5 Space: its dynamic function reserves at least 60 GPU-seconds "
                "and size=xlarge charges quota at 2x. Provider code and policy can change; this does not guarantee acceptance."
            ),
        )

    @staticmethod
    def estimated_quota_seconds(settings: VideoGenerationSettings) -> float:
        frames = 361 if settings.auto_length else max(
            25, int(round(float(settings.duration_seconds) * 24)) // 8 * 8 + 1
        )
        pixels = settings.height * settings.width * frames
        decoder_cost = 20 if settings.decoder == "diffusion" else 8
        reservation = min(400, max(60, int(30 + pixels / 1_500_000 + decoder_cost)))
        return float(reservation * 2)  # The reviewed Space declares size="xlarge", charged at 2x quota.

    def _dependencies(self):
        if self._client_factory and self._handle_file_factory:
            return self._client_factory, self._handle_file_factory
        try:
            from gradio_client import Client, handle_file
        except ImportError as exc:
            raise VideoProviderNotConfiguredError(
                "gradio_client is not installed. Install the optional video dependency."
            ) from exc
        return Client, handle_file

    @classmethod
    def _verify_schema(cls, schema: dict[str, Any], api_name: str) -> None:
        endpoints = schema.get("named_endpoints") if isinstance(schema, dict) else None
        endpoint = endpoints.get(api_name) if isinstance(endpoints, dict) else None
        parameters = endpoint.get("parameters") if isinstance(endpoint, dict) else None
        if not isinstance(parameters, list):
            raise VideoProviderSchemaError("The configured Space did not publish the expected /run schema.")
        names = {
            parameter.get("parameter_name") or parameter.get("name")
            for parameter in parameters
            if isinstance(parameter, dict)
        }
        if not cls.expected_parameters.issubset(names):
            missing = ", ".join(sorted(cls.expected_parameters - names))
            raise VideoProviderSchemaError(f"The LTX Space API schema changed; missing parameters: {missing}.")

    @staticmethod
    def _provider_event_id(job: Any) -> str | None:
        direct = getattr(job, "job_id", None)
        if direct:
            return str(direct)
        communicator = getattr(job, "communicator", None)
        event_id = getattr(communicator, "event_id", None) if communicator else None
        return str(event_id) if event_id else None

    @staticmethod
    def _status_code(job: Any) -> str:
        update = job.status()
        code = getattr(update, "code", update)
        return str(getattr(code, "value", code)).upper()

    @staticmethod
    def _normalize_result(result: Any) -> tuple[Path, str | None, int | None]:
        values = result if isinstance(result, (list, tuple)) else [result]
        if not values:
            raise VideoProviderError("The provider returned no output.")
        output = values[0]
        if isinstance(output, dict):
            output = output.get("path")
        elif hasattr(output, "path"):
            output = output.path
        if not isinstance(output, (str, os.PathLike)):
            raise VideoProviderError("The provider did not return a downloaded video file.")
        prompt = values[1] if len(values) > 1 and isinstance(values[1], str) else None
        seed = None
        raw_seed = values[2] if len(values) > 2 else None
        if isinstance(raw_seed, (int, float)) and not isinstance(raw_seed, bool):
            numeric_seed = float(raw_seed)
            if math.isfinite(numeric_seed) and numeric_seed.is_integer() and 0 <= numeric_seed <= 2_147_483_647:
                seed = int(numeric_seed)
        return Path(output), prompt, seed

    @staticmethod
    def _exception_status(exc: Exception) -> int | None:
        for current in (exc, getattr(exc, "__cause__", None), getattr(exc, "__context__", None)):
            if current is None:
                continue
            response = getattr(current, "response", None)
            value = getattr(response, "status_code", None) if response is not None else None
            if value is None:
                value = getattr(current, "status_code", None)
            try:
                if value is not None:
                    return int(value)
            except (TypeError, ValueError):
                continue
        return None

    @staticmethod
    def _exception_signals(exc: Exception) -> str:
        signals: list[str] = []
        for current in (exc, getattr(exc, "__cause__", None), getattr(exc, "__context__", None)):
            if current is None:
                continue
            signals.extend((type(current).__name__, str(current)))
            response = getattr(current, "response", None)
            if response is not None:
                try:
                    payload = response.json()
                except Exception:
                    payload = None
                if isinstance(payload, dict):
                    for key in ("error", "message", "detail", "status"):
                        value = payload.get(key)
                        if isinstance(value, (str, int, float)):
                            signals.append(str(value))
        return " ".join(signals).lower()

    @classmethod
    def _translate_error(cls, exc: Exception) -> VideoProviderError:
        if isinstance(exc, VideoProviderError):
            return exc
        status = cls._exception_status(exc)
        signal = cls._exception_signals(exc)
        name = type(exc).__name__.lower()
        if status in {401, 403} or any(term in signal for term in ("authenticationerror", "unauthorized", "invalid token", "credentials were not provided")):
            diagnostic = "hf_auth_401" if status == 401 else "hf_auth_403" if status == 403 else None
            return VideoProviderAuthenticationError(
                "Hugging Face rejected the configured credentials.", diagnostic_code=diagnostic
            )
        if isinstance(exc, TimeoutError) or "timeout" in name or "timed out" in signal:
            return VideoProviderTimeoutError("Hugging Face generation exceeded the configured timeout.")
        reservation_terms = ("requested vs", "requested duration", "requested gpu", "requested")
        remaining_terms = (" left", "remaining quota", "remaining gpu")
        if "quota" in signal and any(term in signal for term in reservation_terms) and any(term in signal for term in remaining_terms):
            return VideoProviderReservationError(
                "This request's ZeroGPU reservation exceeds the remaining quota. Choose lower-resource settings or wait for reset."
            )
        if "quota" in signal and any(term in signal for term in ("quota exhausted", "0s left", "no gpu quota remains")):
            return VideoProviderQuotaExhaustedError("Hugging Face reports that the ZeroGPU quota is exhausted.")
        if "quota" in signal and any(term in signal for term in ("quota exceeded", "insufficient quota")):
            return VideoProviderQuotaError(
                "Hugging Face reported insufficient ZeroGPU quota, but did not provide enough detail to distinguish exhaustion from a larger reservation."
            )
        if status == 429 or "toomanyrequests" in name or "rate limit" in signal or "too many requests" in signal:
            return VideoProviderRateLimitError("Hugging Face rate-limited the request. No automatic retry was attempted.")
        if "queueerror" in name or any(term in signal for term in ("queue is full", "queue full", "queue capacity", "queue rejected")):
            return VideoProviderQueueRejectedError(
                "The Hugging Face Space queue rejected the request because it is at capacity."
            )
        if status in {400, 422} or "validationerror" in name or "validation failed" in signal or "invalid input" in signal:
            diagnostic = f"hf_request_http_{status}" if status else None
            return VideoProviderRequestValidationError(
                "Hugging Face rejected the generation parameters.", diagnostic_code=diagnostic
            )
        if any(term in signal for term in ("model initialization", "failed to initialize", "failed to load model", "cuda out of memory")):
            return VideoProviderInitializationError("The Hugging Face Space could not initialize the model.")
        if status in {500, 502, 503, 504} or any(term in signal for term in ("space unavailable", "temporarily unavailable", "service unavailable", "connectionerror")):
            return VideoProviderUnavailableError("The Hugging Face Space is temporarily unavailable.")
        return VideoProviderUnknownError(
            "Generation failed. The provider did not return enough information to identify the exact cause."
        )

    def generate(
        self,
        request: VideoGenerationRequest,
        image_path: Path,
        output_dir: Path,
        state_callback: Callable[[str, str | None], None],
    ) -> VideoProviderResult:
        if not self.capabilities().configured:
            raise VideoProviderNotConfiguredError(self.capabilities().note)
        output_dir.mkdir(parents=True, exist_ok=True)
        Client, handle_file = self._dependencies()
        client = None
        try:
            client = Client(
                self.config.space_id,
                token=self.config.token,
                max_workers=1,
                verbose=False,
                download_files=str(output_dir),
                analytics_enabled=False,
                httpx_kwargs={"timeout": 60},
            )
            schema = client.view_api(return_format="dict")
            self._verify_schema(schema, self.config.api_name)
            settings = request.settings
            job = client.submit(
                prompt=request.prompt,
                image_path=handle_file(str(image_path)),
                height=settings.height,
                width=settings.width,
                duration_s=settings.duration_seconds,
                seed=settings.seed,
                decoder=settings.decoder,
                auto_len=settings.auto_length,
                randomize_seed=settings.randomize_seed,
                do_enhance=settings.enhance_prompt,
                api_name=self.config.api_name,
            )
            state_callback("SUBMITTED", self._provider_event_id(job))
            deadline = self._clock() + self.config.timeout_seconds
            last_update: tuple[str, str | None] | None = None
            while not job.done():
                if self._clock() >= deadline:
                    job.cancel()
                    raise VideoProviderTimeoutError("Hugging Face generation exceeded the configured timeout.")
                status = self._status_code(job)
                event_id = self._provider_event_id(job)
                mapped = "PROVIDER_QUEUED" if status in {"STARTING", "JOINING_QUEUE", "IN_QUEUE", "SENDING_DATA"} else "RUNNING"
                update = (mapped, event_id)
                if update != last_update:
                    state_callback(mapped, event_id)
                    last_update = update
                self._sleep(self.config.poll_interval_seconds)
            state_callback("DOWNLOADING", self._provider_event_id(job))
            result = job.result(timeout=30)
            source, effective_prompt, effective_seed = self._normalize_result(result)
            if not source.is_file() or source.suffix.lower() != ".mp4":
                raise VideoProviderError("The provider output was not a local MP4 file.")
            destination = output_dir / "generated.mp4"
            if source.resolve() != destination.resolve():
                shutil.copy2(source, destination)
            provider_job_id = self._provider_event_id(job)
            if not provider_job_id:
                raise VideoProviderError("The provider did not expose its queue event identifier.")
            return VideoProviderResult(
                provider_job_id=provider_job_id,
                output_path=str(destination),
                effective_prompt=effective_prompt or request.prompt,
                effective_seed=effective_seed if effective_seed is not None else settings.seed,
            )
        except Exception as exc:
            raise self._translate_error(exc) from exc
        finally:
            close = getattr(client, "close", None) if client else None
            if callable(close):
                close()
