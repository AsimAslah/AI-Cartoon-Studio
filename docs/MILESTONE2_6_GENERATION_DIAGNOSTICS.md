# Milestone 2.6 — Hugging Face generation diagnostics

Status: implemented and mock-tested locally; no inference was submitted and no generated MP4 exists.

## What the previous failure proves

The previous UI message combined quota, HTTP 429, and queue rejection into one category. It therefore does **not** prove that the daily quota was exhausted. The upstream exception needed to distinguish the cause was not preserved as a sanitized diagnostic category.

Confirmed evidence reported for the failed session:

- included quota: 300 GPU-seconds;
- remaining quota near the check: approximately 143.53 GPU-seconds; and
- reset: 2026-11-24 20:37 UTC (2026-11-25 02:07 in Asia/Kolkata).

The public `Lightricks/LTX-2.5` Space source currently declares `@spaces.GPU(duration=_duration, size="xlarge")`. Its dynamic reservation has a 60-second minimum, and Hugging Face documents that xlarge consumes quota at 2×. The 1024×576, one-second, conv-decoder preset therefore requests 60 GPU-seconds and is expected to consume/reserve 120 quota seconds. This is below 143.53 seconds, but acceptance is still not guaranteed: remaining quota can change, queue priority depends partly on remaining quota, rate limits and queue capacity are independent, and provider code can change.

Other current reservation examples from the public formula:

- 1024×576, 1 second, conv: about 120 quota seconds;
- 1024×576, 3 seconds, conv: about 132 quota seconds;
- 1024×576, 3 seconds, diffusion (the previous UI default): about 156 quota seconds;
- 1024×576, 5 seconds, conv: about 170 quota seconds; and
- automatic length: substantially higher because the Space reserves for its full worst-case frame cap.

If the failed attempt used the previous three-second diffusion default while 143.53 seconds remained, the public formula makes an oversized reservation a strong hypothesis because 156 exceeds 143.53. Five seconds, automatic length, or less quota at submission time would also make insufficient reservation plausible. If it used the new low-resource preset with 143.53 seconds still remaining, HTTP rate limiting, queue capacity, or another provider failure remains plausible. Prompt enhancement may separately consume quota on its own ZeroGPU Space. The old message cannot resolve the ambiguity retrospectively because the exact settings and sanitized upstream category were not recorded.

## New diagnostic behavior

Provider failures are mapped to sanitized public categories without returning upstream bodies, authorization headers, URLs, or tokens:

| Error code | Meaning |
|---|---|
| `authentication_required` | HTTP 401/403 or an explicit authentication failure |
| `zero_gpu_quota_exhausted` | Evidence explicitly says no quota remains |
| `zero_gpu_quota_insufficient` | Quota was rejected without enough detail to distinguish exhaustion from reservation size |
| `zero_gpu_reservation_exceeds_remaining` | The provider reports requested GPU time greater than remaining quota, or the refreshed quota is below the reviewed estimate |
| `rate_limited` | HTTP 429/TooManyRequests without quota-specific evidence |
| `queue_rejected` | Gradio queue capacity rejection |
| `provider_unavailable` | Space/service unavailable |
| `model_initialization_failed` | Model load, initialization, or CUDA initialization failure |
| `provider_request_rejected` | HTTP 400/422 or provider input validation failure |
| `provider_schema_changed` | `/run` no longer contains the reviewed inputs |
| `provider_timeout` | Network or configured generation timeout |
| `provider_failure_unknown` | Insufficient evidence; a generic safe message is shown |

Each failed job also stores a sanitized `diagnostic_code`. No automatic retry occurs after quota, billing, queue, rate-limit, validation, or provider failures.

## Read-only quota status

The optional video dependency now requires `huggingface_hub>=2.1,<3`. Its official `HfApi.get_zero_gpu_quota()` returns values in GPU-seconds.

Local-only endpoints:

- `GET /api/video/quota` returns only the cached state and never contacts Hugging Face.
- `POST /api/video/quota/refresh` performs one read-only authenticated quota request and never invokes the Space.

The response includes included quota, remaining quota, reset time, last successful refresh, and authentication/permission state. `overquota_used` and other billing details are deliberately not exposed. A fine-grained token needs `Billing > Read billing usage and payment method status` to read quota; the application reports missing permission and does not request it automatically.

## Low-resource diagnostic preset

The UI provides **Use low-resource test preset**. Selecting it changes controls only and never submits:

- LTX-2.5;
- 1024×576;
- 1 second;
- conv decoder;
- seed 42;
- randomization off;
- prompt enhancement off;
- automatic length off; and
- one attempt, with no retry.

The UI discloses the observed 120 GPU-second reservation estimate and states that it cannot guarantee acceptance. A known cached quota below the selected settings' reviewed reservation is rejected before job creation.

## Manual verification gate

Before one future real attempt:

1. Launch from a PowerShell process containing an explicit `AI_CARTOON_HF_TOKEN`; never paste it into chat.
2. Confirm `ffprobe -version` and application discovery.
3. Confirm the provider reports **PROVIDER AVAILABLE**.
4. Select **Refresh quota status** and record remaining quota/reset.
5. Select the low-resource preset and verify every control.
6. Upload the explicitly approved Sheru Bhai image locally.
7. Review the exact prompt and remote-upload disclosure.
8. Obtain explicit approval for one attempt and possible ZeroGPU/prepaid-credit consumption.
9. Click **GENERATE VIDEO** once; do not retry automatically.
10. If completed, record the provider event ID, validate the MP4 with `ffprobe`, and perform independent playback and human visual inspection.

Technical completion is not visual acceptance. Lion identity, suit, jewelry, watch motion, Doberman identity, interior, exterior movement, distortion, extra characters, and continuity must be reviewed by a human.

## References

- Hugging Face quota API: <https://huggingface.co/docs/huggingface_hub/main/guides/manage-spaces#track-your-zerogpu-quota>
- ZeroGPU duration and xlarge quota behavior: <https://huggingface.co/docs/hub/spaces-zerogpu>
- Official LTX-2.5 Space: <https://huggingface.co/spaces/Lightricks/LTX-2.5>
- Gradio Python Client: <https://www.gradio.app/docs/python-client/client>
