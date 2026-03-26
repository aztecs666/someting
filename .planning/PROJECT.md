# Real Data Planner

## What This Is

This repository is a Python freight-planning project with a Flask dashboard, SQLite-backed data pipeline, and ML forecasting workflows. It is intended to ingest real quote or benchmark history, train forecasting artifacts, and support route-planning analysis without presenting synthetic benchmark behavior as real commercial pricing.

## Core Value

The planner must produce defensible, clearly-labeled forecasts from the repo's real data sources without failing on obvious runtime issues.

## Requirements

### Validated

- ✓ SQLite-backed real-data ingestion, benchmark sync, and ML training flows exist in the codebase
- ✓ Flask dashboard and CLI entry points exist for inspection and operational use
- ✓ Codebase mapping artifacts exist under `.planning/codebase/`

### Active

- [ ] Restore the documented GSD planning workflow so work starts from tracked project state
- [ ] Identify concrete runtime, data, and workflow issues in the current codebase
- [ ] Fix issues one by one with verification after each change
- [ ] Keep commits atomic and detailed so the repair history is auditable

### Out of Scope

- New product features unrelated to current defects — the immediate goal is reliability and workflow correction
- Replatforming away from Flask/SQLite/XGBoost — no evidence yet that architecture replacement is needed
- Broad UI redesign of the legacy sandbox dashboard — documentation already labels it as non-core

## Context

The repository already contains a generated codebase map in `.planning/codebase/`, but the primary GSD files referenced by `AGENTS.md` were missing when this session started. Initial inspection surfaced at least one concrete runtime defect in `pipeline/build_train_data.py` where `warnings.warn(...)` is used without importing `warnings`. The repo also has no automated test suite, so validation must rely on targeted smoke checks, import checks, and command execution against the existing database and model artifacts.

## Constraints

- **Tech stack**: Python, Flask, pandas, scikit-learn, XGBoost, SQLite — existing code and artifacts depend on this stack
- **Workflow**: Follow `AGENTS.md` and maintain `.planning/` state — the repo explicitly requires it
- **Safety**: Do not revert unrelated user changes or untracked planning/tooling files — the worktree is already dirty
- **Validation**: No existing tests — each fix needs explicit manual or script-based verification

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Recreate missing `.planning` core files before code fixes | `AGENTS.md` says they are required for starting and tracking work | — Pending |
| Prioritize concrete runtime failures before wider cleanup | Immediate execution blockers provide the highest-confidence fixes | — Pending |
| Keep fixes and commits atomic | Matches repo workflow and reduces regression risk | — Pending |

---
*Last updated: 2026-03-26 after initial GSD restoration and repository audit start*
