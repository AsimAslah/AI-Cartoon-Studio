# GitHub workflow

1. Create a meaningful issue with acceptance criteria.
2. Create one scoped `feature/...` branch.
3. Implement, test, visually inspect Blender changes, and update documentation.
4. Commit with a descriptive conventional message.
5. After explicit approval, push the branch and open a pull request.
6. Require successful CI and review before merging; never rewrite shared history.

The remote is expected to be `https://github.com/AsimAslah/AI-Cartoon-Studio`, but it must be verified before configuration. Repository settings and topics must not be changed without explicit approval.

## Active v0.2.0 workflow

- Issue: [#3 — Storyboard Editor and Project Persistence](https://github.com/AsimAslah/AI-Cartoon-Studio/issues/3)
- Branch: `feature/storyboard-editor`, created from released v0.1.0 `main`
- Required before merge: local pytest/compile checks, optional Blender smoke test, published feature branch, pull request CI, review, and explicit user merge approval
- The v0.2.0 pull request must not be merged automatically.
