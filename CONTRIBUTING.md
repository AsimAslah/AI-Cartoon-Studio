# Contributing

Use a genuine issue → branch → pull request workflow for meaningful changes. Include acceptance criteria, tests, and accurate documentation. Suggested branches use `feature/<name>` and commits use clear conventional prefixes such as `feat:`, `fix:`, `test:`, or `docs:`.

Before opening a pull request, activate `.venv`, run `python -m pytest` and `python -m compileall -q app scripts tests`, then run `node --check` for modified JavaScript files. For Blender changes, also run the local demo and inspect both the PNG and MP4. For timeline/export changes, validate real FFmpeg output with FFprobe. Never add API keys, private media, generated outputs, unlicensed assets, fabricated screenshots, fake collaborators, or activity created only to pursue an achievement.
