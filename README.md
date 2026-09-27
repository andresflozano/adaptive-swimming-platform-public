# Adaptive Swimming Platform

A deterministic Python reference implementation for representing swimming workouts, mapping distance-based intent to pool lengths, recording versioned session evidence, evaluating explicit rules, and producing human-reviewed adaptation proposals.

## Public snapshot scope

This repository is a sanitized public demonstration snapshot. It contains:

- Python domain, evaluation, planning, persistence, presentation, recording, and source-program modules;
- deterministic synthetic workout fixtures;
- automated unit and workflow tests;
- no original source documents;
- no private corpus manifests;
- no personal session records;
- no private conversation references;
- no private repository history.

Synthetic source identity:

```text
source_id: SRC_8C962466BDCC
source_sha256: 8c962466bdcc1efa53f61787f84e6b6a216c4c5e6d0939520baa2d61d372b008
session_id: WT_SRC_8C962466BDCC_POOL_D01_V1
```

## Implemented capabilities

- immutable workout and session-result models;
- deterministic distance and rest calculations;
- explicit known and unresolved timing coverage;
- proposal, acceptance, review, and no-overwrite persistence boundaries;
- provider-neutral pool geometry and distance-to-length mapping;
- immutable mapped workout plans with explicit error reporting;
- provider-neutral completed-length reconciliation;
- manual and device observations kept separate from reviewed interpretations;
- human review before applying workout or target changes.

The current implementation is a local Python and JSON system. It does not claim production, cloud, multi-user, medical, or training-science validation.

## Repository layout

```text
src/adaptive_swimming/   Application packages
scripts/                 Operator and export workflows
tests/                   Unit and workflow regression coverage
data/examples/           Synthetic source fixture
data/golden/             Generated synthetic golden workout
```

## Local setup

```bash
uv sync
```

## Validation

```bash
uv run ruff check .
uv run mypy
uv run pytest -q
uv lock --check
```

Validated during snapshot creation:

```text
Ruff: passed
Mypy: passed across 106 source files
Pytest: 511 passed
Lockfile: passed
```

## Safety and privacy

The software is advisory. It does not diagnose injuries, prescribe medical alternatives, or replace professional coaching or healthcare guidance.

Do not commit personal training records, exported wearable activities, source documents, credentials, or private conversation material. Use synthetic fixtures for public examples and tests.

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE).
