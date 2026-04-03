# Real Data Planner

## What This Is

This repository is a Python freight-planning project with a Flask dashboard, SQLite-backed data pipeline, and ML forecasting workflows. It trains forecasting artifacts from public benchmark market data (Compass/Xeneta) and provides route-planning analysis. The system clearly labels all outputs as benchmark-backed, not commercial quote-backed.

## Core Value

The planner must produce defensible, clearly-labeled forecasts from the repo's real data sources without failing on obvious runtime issues.

## Requirements

### Validated

- [x] SQLite-backed real-data ingestion, benchmark sync, and ML training flows exist in the codebase
- [x] Flask dashboard and CLI entry points exist for inspection and operational use
- [x] Codebase mapping artifacts exist under .planning/codebase/
- [x] Forecasting outputs are clearly labeled as benchmark-backed
- [x] Forecast writes are transactional; audit is read-only
- [x] Retrain endpoint restricted to localhost; explicit busy status
- [x] Unsupported lane fallbacks fail explicitly
- [x] Observable predictor stage retired with clear messaging
- [x] All ML dependencies pinned; runtime manifests generated on train
- [x] Repository hygiene improved; stray files and duplicate data removed

### Active

- None — all v1 requirements are complete

### Out of Scope

- New product features unrelated to current defects
- Replatforming away from Flask/SQLite/XGBoost
- Broad UI redesign of the legacy sandbox dashboard
- v2 hardening requirements (tests, auth, config externalization)

## Context

The repository was audited and repaired across 4 phases. Phase 3 addressed data and forecast integrity issues identified in a cross-AI review. Phase 4 tightened repo hygiene by removing stray files and hardening the gitignore.

Key findings from cross-AI review (2026-04-03):
- The model is trained on benchmark market data (17,780 rows), not commercial quote data (0 rows)
- All outputs now carry explicit provenance labels
- The system behaves honestly as a benchmark-driven prototype

## Constraints

- **Tech stack**: Python, Flask, pandas, scikit-learn, XGBoost, SQLite
- **Workflow**: Follow AGENTS.md and maintain .planning/ state
- **Validation**: No automated tests — each fix uses manual smoke tests

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Recreate missing .planning core files before code fixes | AGENTS.md says they are required for starting and tracking work | Done — Phase 1 complete |
| Prioritize concrete runtime failures before wider cleanup | Immediate execution blockers provide the highest-confidence fixes | Done — Phase 2 complete |
| Keep fixes and commits atomic | Matches repo workflow and reduces regression risk | Done — 11 commits across Phases 1-4 |
| Relabel product as benchmark-driven prototype | Prevent overclaiming without real quote data | Done — Phase 3 provenance commit |
| Retire observable predictor stage | No reproducible supervised targets exist in repo | Done — Phase 3 |

---
*Last updated: 2026-04-03 after Phase 3 and Phase 4 completion*