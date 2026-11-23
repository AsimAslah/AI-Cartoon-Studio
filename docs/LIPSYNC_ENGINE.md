# Malayalam Lip-Sync Engine — incremental implementation plan

> Historical Step 2 document. Milestone 1 now extends this contract with safe persistence, previews, provider discovery, and truthful background-job contracts. See [LIPSYNC_MILESTONE1.md](LIPSYNC_MILESTONE1.md). Real inference remains unavailable.

## This step: contract only

- `app/services/lipsync_contract.py` provides typed input modes, Malayalam language metadata, size / format checks, a provider protocol, and a deliberately unavailable default adapter.
- `tests/test_lipsync_contract.py` exercises this foundation offline on CPU.
- This step does **not** add a UI, FastAPI endpoint, real lip-sync model, or generated video. It cannot be used to claim successful lip synchronization.
- File signatures are a preliminary check; a future endpoint must validate decoded duration, dimensions, codec, safe storage and output before a provider is invoked.

## Next stages

1. Add authenticated/local-only FastAPI upload + job endpoints, safe UUID storage, limits, and consistent status reporting. Preserve existing storyboard and render APIs.
2. Add one opt-in provider implementation and test its availability, legal commercial use, capacity, and compatibility with lion/goat/tiger/dog faces. Show any API cost before submission; never charge silently.
3. Generate Malayalam voice WAV separately, preserve it, and use it as lip-sync input.
4. Validate a 3–5 second Sheru Bhai speaking close-up (real animal mouth articulation) and export an MP4 only if an actual render completes.

## Upstream reference

Studied `Anil-matcha/Open-Generative-AI` — `packages/studio/src/components/LipSyncStudio.jsx` and `packages/studio/src/muapi.js`. Their image/video+audio UX and job lifecycle are useful references, but most hosted endpoints rely on a paid MuAPI key. This module is fresh Python code, not a copy of that repository.
