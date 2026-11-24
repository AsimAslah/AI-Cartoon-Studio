# Milestone 2.7 — first real AI-video verification

Verification date: 2026-11-24.

Status: **one real provider-generated MP4 is technically verified and visually inspected.** This milestone did not submit another inference request or consume additional Hugging Face quota.

## Preserved artifact

The successful application output remains in the ignored runtime-data directory:

`output/video_generation_jobs/6f04c42b-aaa8-432f-9c8d-66b0c5a70ff3/generated.mp4`

The job directory also contains the provider-downloaded copy. Both files are 328,928 bytes and have the same SHA-256 digest:

`02d74f5ae77d85a805cec55cc75b6baa69cb8819a85fdcb58188eb90b3c0c191`

This confirms that the canonical `generated.mp4` is byte-identical to the preserved downloaded result. Neither file is committed to Git.

## Technical verification

FFprobe 9.1 successfully decoded the container and reported:

| Property | Verified value |
|---|---|
| Container | ISO Base Media / MP4 |
| Duration | 1.041667 seconds |
| Resolution | 1024×576 |
| Frame rate | 24 fps |
| Video frames | 25 |
| Video codec | H.264/AVC High profile (`avc1`) |
| Pixel format | YUV 4:2:0 progressive (`yuv420p`) |
| Audio | AAC-LC, stereo, 48 kHz |
| File size | 328,928 bytes |
| FFprobe score | 100 |

All 25 decoded video frames produced distinct frame hashes. This is evidence of temporal image changes and rules out a file made entirely from one duplicated frame. It is not, by itself, a quality or character-consistency guarantee.

## Provider and generation record

The application has one allowlisted provider for this workflow:

- provider: Hugging Face Space `Lightricks/LTX-2.5`;
- application provider ID: `huggingface_ltx_2_5`;
- configured model identity: `Lightricks/LTX-2.5-Diffusers`; and
- endpoint: `/run`.

The MP4 container does not embed provider, model, prompt, seed, decoder, or queue-event metadata. Video job records are currently held only in server memory. The original server session was no longer running during Milestone 2.7 verification, so the following values cannot be recovered from the preserved artifact:

- provider event ID;
- exact submitted prompt and effective provider prompt;
- seed and whether seed randomization was enabled;
- `conv` versus `diffusion` decoder;
- prompt-enhancement and automatic-length toggles; and
- the exact requested duration.

The output itself verifies 1024×576 and approximately one second. These characteristics are consistent with the low-resource diagnostic preset, but they do not prove that every preset value was submitted. The associated preserved upload record identifies a 1672×941 convoy reference prepared shortly before the successful job, but private source media remains ignored and uncommitted.

## Visual observations

Five evenly sampled frames and a full-resolution midpoint frame were inspected against the preserved reference image.

Confirmed visible content:

- a black luxury sedan resembling a Rolls-Royce leads a convoy of black vehicles;
- the vehicles travel on a divided highway with palms, green fields, and hills resembling Kerala scenery;
- a white anthropomorphic lion and a dark chauffeur remain visible through the windshield; and
- vehicle/background positions change across the 25 unique frames, producing a short moving exterior shot.

Observed limitations:

- the shot is an exterior frontal tracking view, not an interior medium close-up;
- the lion remains recognizable in broad color and silhouette, but facial structure, mane detail, cream suit, jewelry, sunglasses, and wristwatch are softened or altered;
- a wrist-lowering or time-checking action cannot be verified from this short exterior view;
- the chauffeur remains present, but distinct black-Doberman facial identity is not reliably preserved;
- the grille, hood ornament, license plate, occupants, and following vehicles vary in fine detail relative to the reference; and
- the one-second duration is too short to assess longer-term identity, motion continuity, or advertisement pacing.

Technical completion therefore does not equal visual acceptance. This clip is usable as proof that the real image-to-video pipeline returned and validated an animated MP4, but it is not accepted as a complete character-consistent WOODORA advertisement shot.

## Remaining work

Before producing a multi-clip advertisement:

1. Persist a sanitized job manifest alongside each result so provider event ID, prompt, effective prompt, seed, decoder, toggles, and verified metadata survive server restarts.
2. Define shot-specific reference images and acceptance criteria for Sheru Bhai, the chauffeur, vehicle details, wristwatch action, and camera composition.
3. Generate future clips only through separately approved, quota-aware attempts.
4. Visually review every clip before it enters an edit.
5. Implement real multi-clip sequencing, transitions, audio handling, and final-export verification; these are not provided by the current single-job workflow.
6. Keep Malayalam lip-sync separate until a real provider produces a visibly synchronized, independently verified MP4.

Milestone 2.7 stops at verification and documentation. It does not start Milestone 3 or Milestone 4.
