# Image-to-video provider research

Research date: 2026-11-24.

## Selected integration: Lightricks LTX-2.5 on Hugging Face

The official `Lightricks/LTX-2.5` public Gradio Space was selected over the older LTX-2.3 demonstration because it is the newer official Lightricks option and exposes a programmatic Gradio endpoint. Its published OpenAPI/Gradio schema identifies `/run` with these parameters:

`prompt`, `image_path`, `height`, `width`, `duration_s`, `seed`, `decoder`, `auto_len`, `randomize_seed`, and `do_enhance`.

The reviewed bounds were 512–1536 pixels for height/width, 1–5 seconds duration, 0–2,147,483,647 seed, and `diffusion`/`conv` decoder. The endpoint returns a downloaded video object plus effective prompt, seed, and a status string. The adapter verifies parameter names at runtime rather than assuming that a public demo is stable.

Gradio's official Python client supports `Client.view_api()`, `Client.submit()`, `handle_file()`, queue/job status, result download, and cancellation. The implementation uses those supported mechanisms and does not scrape the web UI.

## Authentication and quota

An explicit `AI_CARTOON_HF_TOKEN` is required by this application even though a public Space may accept anonymous access. This prevents accidental reuse of a token cached by another Hugging Face application and makes the remote identity/quota boundary visible to the operator.

Hugging Face documents finite ZeroGPU daily GPU quotas, with lower allowances for unauthenticated/free users and higher allowances or prepaid access for paid plans. These values and policies are provider-controlled and can change, so the application labels generation as quota/cost-bearing and does not promise a free request.

The public LTX-2.5 Space source inspected on 2026-11-24 uses a dynamic `@spaces.GPU` duration and `size="xlarge"`. The function reserves at least 60 GPU-seconds; Hugging Face documents that xlarge consumes quota at 2×. Consequently, even a one-second request can require an observed 120 quota seconds. Remaining daily quota does not guarantee acceptance because reservation size, queue capacity, rate limits, and provider availability are separate constraints.

## Hardware and output

Inference runs on Hugging Face server-side GPU hardware. The local integrated AMD Radeon system is not asked to execute LTX weights, and no multi-gigabyte model is downloaded. The local computer needs only the application, `gradio_client`, network access, and `ffprobe` for independent result validation. The accepted final artifact is a local MP4 whose video stream, dimensions, duration, frame rate, and codec are verified.

## Licensing and programmatic access

LTX source code and LTX model weights are not necessarily governed by the same license. The model repository points to the applicable LTX community/model license. Users must review the current model card, license, Hugging Face terms, acceptable-use rules, and commercial-use conditions before production or commercial deployment.

A public Gradio UI does not imply unlimited API use. The adapter uses the documented Gradio API, observes authentication and queue errors, applies a bounded timeout, performs no automatic retry, and makes no attempt to bypass quota, payment, or access controls.

## Alternatives considered

- **LTX-2.3:** official and compatible in principle, but older than the selected LTX-2.5 Space and not needed for the first adapter.
- **Wan image-to-video:** capable open-weight families exist, but typical local deployments require CUDA-class GPU memory unavailable on this laptop. No arbitrary community Space was allowlisted without an equally exact schema/license review.
- **Local Diffusers/ComfyUI:** excluded from this milestone because downloading and running multi-gigabyte video models on an integrated Radeon laptop would violate the hardware and no-large-download constraints.
- **Commercial proprietary APIs:** not enabled. No account, payment method, or cloud resource is created automatically.

The provider interface remains extensible, but every future backend must receive its own endpoint, authentication, license, cost, SSRF, and output-verification review.

## Official references

- Hugging Face Spaces API endpoints: <https://huggingface.co/docs/hub/spaces-api-endpoints>
- Gradio Python Client: <https://www.gradio.app/docs/python-client/client>
- Gradio job interface: <https://www.gradio.app/docs/python-client/job>
- Official LTX-2.5 Space: <https://huggingface.co/spaces/Lightricks/LTX-2.5>
- Official LTX-2.5 Diffusers model: <https://huggingface.co/Lightricks/LTX-2.5-Diffusers>
- Hugging Face ZeroGPU quotas: <https://huggingface.co/docs/hub/spaces-zerogpu>
