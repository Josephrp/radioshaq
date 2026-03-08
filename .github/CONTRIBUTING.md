# Contributing to RadioShaq

Thanks for contributing.

## Branch and Merge Policy

The repository enforces the following flow:

1. Create feature/fix branches from `dev`.
2. Open pull requests into `dev` for integration.
3. Merge `dev` into `main` for stable releases only.

Pull requests targeting `main` must come from `dev`. Direct pushes to `main` are not part of the intended process.

## Release Lanes

The project uses two release lanes:

1. `dev` lane: nightly prerelease builds (PyPI prerelease versions).
2. `main` lane: stable release builds (standard version tags and PyPI stable versions).

Version changes must stay consistent across:

1. Python package metadata.
2. Runtime package version constants.
3. API advertised version.
4. Web interface package version.

## Licensing

This project is licensed under GPL-2.0-only. Contributions are accepted under the same license.

By submitting a contribution, you confirm you have rights to submit it under GPL-2.0-only and that your contribution does not introduce licensing conflicts.

## License Acceptance in Official Clients

Official clients require explicit user acceptance of the GPL terms before normal use:

1. CLI flow requires acceptance before command execution.
2. Web UI requires acceptance before app interaction.

If you modify entrypoints, preserve these acceptance checks.

## Pull Request Expectations

Each pull request should include:

1. A concise summary of behavior changes.
2. Tests or rationale for test gaps.
3. Any release/version implications.
4. Any licensing or compliance impact.

If a change affects release workflows, branch policy enforcement, or licensing gates, include explicit validation notes in the PR description.

## Local Test Workflow (before commit)

Run from repository root:

```bash
cd radioshaq
uv sync --extra dev --extra test --extra sdr
uv run pytest tests/unit tests/integration -v
cd ..
python radioshaq/scripts/check_version_sync.py
```

What this covers:

1. Full unit test suite.
2. Full integration test suite used by CI.
3. Version consistency guard across package/runtime surfaces.

## Git Hook: run all tests before push

This repository provides a managed pre-push hook in `.githooks/pre-push`.
There is currently no managed `pre-commit` hook in this repository.

Enable it once per clone:

```bash
git config core.hooksPath .githooks
# Linux/macOS only:
chmod +x .githooks/pre-push
```

Verify your local clone is configured:

```bash
git config --get core.hooksPath
```

Expected output:

```text
.githooks
```

Then every `git push` runs:

1. `python radioshaq/scripts/check_version_sync.py`
2. `uv sync --extra dev --extra test --extra sdr`
3. `uv run pytest tests/unit tests/integration -v`

Push is blocked if any step fails.

## Development Runtime Workflows (Docker Compose + PM2)

Run from repository root unless noted otherwise.

### Workflow A: Docker Compose + direct API process

```bash
cd radioshaq
uv sync --extra dev --extra test --extra sdr

# Start Postgres only
radioshaq launch docker

# Optional: start Postgres + Hindsight profile
# radioshaq launch docker --hindsight

# Run migrations
python infrastructure/local/run_alembic.py upgrade head

# Start API (foreground)
radioshaq run-api
```

Verify:

1. API health: `http://localhost:8000/health`
2. API docs: `http://localhost:8000/docs`
3. Web UI: `http://localhost:8000/`

Shutdown:

```bash
docker compose -f infrastructure/local/docker-compose.yml down
```

### Workflow B: Docker Compose + PM2 managed API

```bash
cd radioshaq
uv sync --extra dev --extra test --extra sdr

# PM2 workflow starts Docker Postgres first when available
radioshaq launch pm2

# Optional: include Hindsight
# radioshaq launch pm2 --hindsight
```

PM2 operations:

```bash
pm2 status
pm2 logs radioshaq-api
pm2 restart radioshaq-api
pm2 stop radioshaq-api
pm2 delete radioshaq-api
```

If Hindsight was started under PM2, manage it similarly with `hindsight-api`.

### Manual Docker Compose commands (when not using `radioshaq launch`)

```bash
cd radioshaq
docker compose -f infrastructure/local/docker-compose.yml up -d postgres
# Optional hindsight profile:
# docker compose -f infrastructure/local/docker-compose.yml --profile hindsight up -d postgres hindsight
python infrastructure/local/run_alembic.py upgrade head
radioshaq run-api
```

## Release: selecting versions and pushing tags to main

Stable publish is triggered by pushing a tag matching `v*` and validated against `origin/main`.

### Select the version before release

Recommended on `dev`:

1. Use workflow dispatch:
   1. `Prepare Patch Release (dev)` for `X.Y.Z+1`.
   2. `Prepare Minor Release (dev)` for `X.Y+1.0`.
   3. `Prepare Major Release (dev)` for `X+1.0.0`.
2. Or bump locally:

```bash
python radioshaq/scripts/bump_version.py --project-root . --bump patch --sync-all
# or explicit version:
python radioshaq/scripts/bump_version.py --project-root . --set-version 0.2.0 --sync-all
```

Always validate after bump:

```bash
python radioshaq/scripts/check_version_sync.py
```

### Push stable tag from main

1. Merge `dev -> main` through PR.
2. Update local main:

```bash
git fetch origin
git checkout main
git pull origin main
python radioshaq/scripts/check_version_sync.py
```

3. Create annotated tag that matches package version:

```bash
git tag -a v0.2.0 -m "Release v0.2.0"
```

4. Push tag:

```bash
git push origin v0.2.0
```

This starts stable build and publish workflow.
