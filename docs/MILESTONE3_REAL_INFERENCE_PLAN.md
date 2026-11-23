# Milestone 3 plan — real inference and Malayalam lip-sync

Planning status: proposed only. This document does not configure a provider, install software, submit media, consume quota, or claim successful AI generation or lip-sync.

## Evidence and current gates

Milestone 2 provides a real LTX-2.5 Gradio adapter, but only its contract and failure paths have been exercised with mocks. A live request still requires all of the following:

- a reviewed, running provider schema;
- a user-installed `ffprobe.exe` available on `PATH` or through `AI_CARTOON_FFPROBE_PATH`;
- an explicit `AI_CARTOON_HF_TOKEN` supplied in the launch environment;
- `AI_CARTOON_ENABLE_REMOTE_VIDEO=1`;
- informed approval to upload the selected image and prompt and consume provider quota; and
- visual inspection of the returned video.

On 2026-11-24, `ffprobe` was not installed or configured on the development machine, remote generation was disabled, and no token was present. The official public LTX-2.5 Gradio OpenAPI schema still exposed the reviewed `/run` inputs: `prompt`, `image_path`, `height`, `width`, `duration_s`, `seed`, `decoder`, `auto_len`, `randomize_seed`, and `do_enhance`. Fetching that schema did not submit inference.

## Open Generative AI architecture review

Review target: [`Anil-matcha/Open-Generative-AI`](https://github.com/Anil-matcha/Open-Generative-AI) at commit [`6f726e6539b06bb2f4288f20480c116e7173a06d`](https://github.com/Anil-matcha/Open-Generative-AI/tree/6f726e6539b06bb2f4288f20480c116e7173a06d). The repository is MIT-licensed. No source was copied into this project. If substantial code is reused later, its copyright and MIT notice must accompany that reuse.

Reviewed files:

- [`VideoStudio.jsx`](https://github.com/Anil-matcha/Open-Generative-AI/blob/6f726e6539b06bb2f4288f20480c116e7173a06d/packages/studio/src/components/VideoStudio.jsx)
- [`LipSyncStudio.jsx`](https://github.com/Anil-matcha/Open-Generative-AI/blob/6f726e6539b06bb2f4288f20480c116e7173a06d/packages/studio/src/components/LipSyncStudio.jsx)
- [`WorkflowStudio.jsx`](https://github.com/Anil-matcha/Open-Generative-AI/blob/6f726e6539b06bb2f4288f20480c116e7173a06d/packages/studio/src/components/WorkflowStudio.jsx)
- [`models.js`](https://github.com/Anil-matcha/Open-Generative-AI/blob/6f726e6539b06bb2f4288f20480c116e7173a06d/packages/studio/src/models.js)
- [`muapi.js`](https://github.com/Anil-matcha/Open-Generative-AI/blob/6f726e6539b06bb2f4288f20480c116e7173a06d/packages/studio/src/muapi.js)

### Patterns worth adapting

1. **Capability-driven model registry.** `models.js` records model family, endpoint, media fields, prompt requirements, supported modes, resolutions, durations, and feature flags. Our equivalent should remain typed Pydantic provider capabilities, with each backend exposing only reviewed controls.
2. **Explicit generation modes.** `VideoStudio` separates text-to-video, image-to-video, and video-to-video instead of forcing one universal form. Add text-to-video only after a provider endpoint is reviewed; keep it separate from the current image-conditioned request.
3. **Reference slots.** The video UI models start images, end images, audio, video, and multi-image references as named inputs. Introduce a versioned `CharacterReferenceSet` for Sheru Bhai and other recurring characters rather than loose URLs.
4. **Provider-family selection.** Model families and variants are grouped while controls change according to capability metadata. Keep provider choice server-owned so tokens and endpoint allowlists never move into browser JavaScript.
5. **Centralized submission and polling.** `muapi.js` normalizes submit identifiers, bounded polling, outputs, uploads, and errors. Our existing provider adapters and job managers should gain a shared error taxonomy and cancellation contract, while retaining server-side credentials and independent output validation.
6. **Two lip-sync input modes.** `LipSyncStudio` distinguishes image+audio from video+audio and exposes only model-supported prompt/resolution fields. This matches the Milestone 1 contracts and should be preserved.
7. **History as a first-class feature.** Both studios keep generation entries with media URL, model, parameters, and actions. Add durable, local, schema-versioned job manifests so completed/failed jobs survive a server restart; never store secrets in a manifest.
8. **Schema-driven workflows.** `WorkflowStudio` renders inputs from schemas and represents a workflow as nodes and edges. A future local workflow can safely compose `reference image → image-to-video → lip-sync → verified export`, with every node preserving provenance and validation boundaries.
9. **Cinematic controls are capability-gated.** Camera/lens/effect/reference options appear only for supporting models. Do not add decorative controls that the selected provider ignores.
10. **Visible failure and preview states.** Upload, generation, result, history, fullscreen preview, download, and error states are distinct. Continue using truthful backend states rather than fabricated progress percentages.

### Patterns not to adopt

- Do not integrate MuAPI automatically or add a paid dependency without a separate provider, price, privacy, terms, and license review.
- Do not place API keys in browser state, `sessionStorage`, frontend requests, repository configuration, or project manifests.
- Do not accept arbitrary provider output URLs or trust a hosted result without downloading it through the reviewed client and validating it locally.
- Do not import a 1.3 MB untyped model catalogue. Each supported provider needs a small reviewed contract and tests.
- Do not copy marketing claims, model-quality claims, or proprietary model behavior.

## Proposed architecture

```text
CharacterReferenceSet (local UUID, versioned)
             │
             ▼
Image-to-video provider adapter ──► verified source MP4
             │                            │
             │ provenance                 ▼
             └──────────────────► Lip-sync provider adapter
                                          │
                                          ▼
                              verified Malayalam MP4 + report
```

Every provider adapter must declare input modes, animal-support evidence, authentication, pricing/quota, license, hardware location, timeouts, cancellation, and exact output contract. The server owns provider credentials. Each job records provider/model/version, request settings, source media hashes, provider job ID, timestamps, error code, and verified metadata. Original images, videos, and Malayalam audio remain immutable.

## Delivery phases

### Phase 0 — separate issue and branch

After draft PR #7 is reviewed and merged, create a dedicated Milestone 3 issue and branch from updated `main`. Do not implement Milestone 3 inside PR #7. Record provider terms, quota, model license, and input retention policy before adding credentials.

### Phase 1 — enable verification prerequisites

1. User installs a trusted Windows FFmpeg build; record its source and version.
2. Verify `ffprobe -version` and `discover_ffprobe()`.
3. Set `AI_CARTOON_FFPROBE_PATH` only if `ffprobe` is not on `PATH`.
4. Set the Hugging Face token in the current PowerShell process, never in Git.
5. Re-fetch the Space schema and compare it with the allowlisted contract.
6. Start Uvicorn on `127.0.0.1` and confirm the capability endpoint reports ready.

### Phase 2 — one real WOODORA image-to-video proof

Use an approved Sheru Bhai/Rolls-Royce reference image and the documented WOODORA motion prompt. Begin with the lowest practical quota exposure: one 1–3 second request at a supported modest resolution. Before clicking generate, record the provider identity and disclosed quota/cost expectation.

Acceptance evidence:

- a real provider event ID and state history;
- a locally downloaded MP4 that passes envelope and `ffprobe` validation;
- recorded resolution, duration, frame rate, codec, provider, model, prompt, and seed;
- playback in an independent player; and
- human review of lion identity, suit/jewelry, wristwatch motion, Doberman identity, vehicle interior, moving Kerala exterior, unexpected characters, distorted limbs, and scene continuity.

A playable file is technical success, not automatic visual acceptance. Preserve failed outputs and observations as test evidence without labeling them successful.

### Phase 3 — select a Malayalam lip-sync backend

Perform a provider comparison before coding. Candidate families identified by the reference project include image+audio services such as LTX lipsync, InfiniteTalk, and Wan speech-to-video, and video+audio services such as LatentSync. Their listing in another UI is not evidence that their endpoints, pricing, licensing, Malayalam phoneme quality, or animal support are suitable.

Require for each candidate:

- official API or self-hosting documentation and exact schema;
- authentication, price/quota, data retention, and commercial-use terms;
- server GPU and local dependency requirements;
- WAV/MP3 limits and whether audio is resampled;
- tested Malayalam speech preservation with no translation or synthesis;
- output download and cancellation behavior; and
- documented or experimentally demonstrated non-human/animal-face compatibility.

Prefer video+audio lip-sync after the LTX motion clip exists, because it separates scene motion generation from mouth synchronization and lets both stages be evaluated independently. Keep image+audio as a separate provider mode rather than silently changing the workflow.

### Phase 4 — Malayalam and animal trials

Use the original approved Malayalam audio byte-for-byte. Test a short, clearly articulated phrase first on Sheru Bhai, then on the goat character. For each output, compare audible timing with visible mouth closures/openings and record face drift, muzzle deformation, teeth/tongue artifacts, identity loss, and background damage. Human portrait success must not be generalized to lion or goat faces.

### Phase 5 — durable history and composed workflow

After both stages independently pass, add local versioned job manifests and an optional two-node workflow: image-to-video followed by video-to-video lip-sync. A failed second stage must not delete or overwrite the verified source video. Export provenance should identify both providers and models.

## Test plan

- Unit tests: provider schemas, request mapping, error taxonomy, cancellation, timeouts, hashes, manifests, and Malayalam metadata preservation.
- API tests: local-only access, literal remote consent, unavailable credentials/quota, restart-safe history, and safe output retrieval.
- Integration test: schema discovery only; no inference in ordinary CI.
- Manual approved test: one real WOODORA generation, then separate Malayalam lip-sync trials.
- Regression: complete pytest suite plus existing Blender render smoke procedure.

## Milestone 3 completion criteria

Milestone 3 is complete only when one real image-to-video MP4 is produced and independently validated, one Malayalam lip-sync backend is integrated through a reviewed provider contract, synchronization is manually evaluated, and results/limitations for Sheru Bhai and the goat are documented. Animal lip-sync must remain labeled experimental unless the recorded trials visibly pass.
