# Lip-sync and video provider research

Reviewed on 2026-11-24 from the projects' official repositories. No third-party source code or model weights were copied into this repository.

| Project | Relevant pattern | Runtime fit for this computer | License observations | Decision |
|---|---|---|---|---|
| [Open Generative AI](https://github.com/Anil-matcha/Open-Generative-AI) | Portrait/video modes, provider selection, upload previews, asynchronous history | Its hosted model routes commonly require external APIs; the full Next/Electron application is unnecessary here | Repository is MIT licensed | Adapt UX concepts only in original FastAPI/vanilla-JS code |
| [LatentSync](https://github.com/bytedance/LatentSync) | Video + audio lip synchronization and explicit inference pipeline | Official README lists 8 GB VRAM minimum for v1.5 and 18 GB for v1.6, with CUDA dependencies; unsuitable for integrated Radeon | Repository license is Apache 2.0; checkpoint/dependency terms still need release review | Candidate for an external NVIDIA worker; unavailable locally |
| [MuseTalk](https://github.com/TMElyralab/MuseTalk) | Avatar preparation, video/audio inference, reusable character workflow | Official minimum example uses an NVIDIA RTX 3050 Ti with 4 GB VRAM; still incompatible with this non-CUDA machine | README states MIT code/commercial model use while requiring compliance with third-party component licenses | Candidate for a controlled NVIDIA test; unavailable locally |
| [Wan2.2](https://github.com/Wan-Video/Wan2.2) | Text/image/audio-guided cinematic generation and provider settings | Even the consumer-oriented 5B video model targets discrete GPUs such as RTX 4090; unsuitable as a default dependency | Repository uses Apache 2.0; individual weights and dependencies must be checked | Future external video provider, not Milestone 1 lip-sync runtime |
| [LTX-2](https://github.com/Lightricks/LTX-2) | Modular video pipelines and explicit model-component downloads | Current large models and recommended CUDA workflows exceed this hardware | Code is Apache 2.0, but model weights use separate LTX community licenses and commercial terms may apply | Do not install automatically; review exact model license before any provider |
| [AI4Bharat Indic-TTS](https://github.com/AI4Bharat/Indic-TTS) | Malayalam text-to-speech research and models | Voice generation is a separate optional milestone; reference audio/model resources and quality need testing | Repository is MIT licensed; individual Bhashini model/data terms must also be checked | Research candidate for Malayalam Voice Studio, not silently enabled |

## Milestone 2 gate

A real provider is eligible only after all of the following are demonstrated:

- explicit user approval for local installation or external cost;
- compatible NVIDIA/external GPU capacity;
- exact code, model-weight, dataset, and dependency license review;
- credentials stored outside source control and never logged;
- decoded codec/duration/dimensions validation;
- genuine provider execution with captured states and failure details;
- verified MP4 output with visible Malayalam-correlated mouth movement;
- separate human and anthropomorphic-animal compatibility results.

Until then, provider entries remain informational and unavailable.
