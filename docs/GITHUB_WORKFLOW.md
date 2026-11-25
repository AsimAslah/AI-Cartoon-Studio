# GitHub workflow

1. Create a meaningful issue with acceptance criteria.
2. Create one scoped `feature/...` branch.
3. Implement, test, visually inspect Blender changes, and update documentation.
4. Commit with a descriptive conventional message.
5. After explicit approval, push the branch and open a pull request.
6. Require successful CI and review before merging; never rewrite shared history.

The remote is expected to be `https://github.com/AsimAslah/AI-Cartoon-Studio`, but it must be verified before configuration. Repository settings and topics must not be changed without explicit approval.

## Active v0.6.0 release-preparation workflow

- Issue: [#14 — v0.6.0 release preparation](https://github.com/AsimAslah/AI-Cartoon-Studio/issues/14)
- Branch: `chore/release-v0.6.0`, created from the verified Milestone 6 merge on `main`
- Required before merge: full pytest suite, Python compilation, JavaScript syntax/model checks, schema compatibility, dependency consistency, credential/generated-asset audit, documentation review, published branch, successful pull-request CI, and explicit merge approval
- The pull request, release tag, and GitHub release must not be merged or published automatically.
