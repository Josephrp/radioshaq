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
