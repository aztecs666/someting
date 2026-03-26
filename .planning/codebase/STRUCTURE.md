# Codebase Structure

**Analysis Date:** 2026-03-26

## Directory Layout

```text
[project-root]/
├── app/                    # Flask runtime, streaming engine, planner support, generated planner artifacts
├── data/                   # SQLite DB, observable ingestion code, external data fetchers
├── pipeline/               # Orchestration scripts and feature-building modules
├── ml/                     # Model training, evaluation, health checks, benchmark artifacts
├── scripts/                # Thin executable wrappers around package modules
├── utils/                  # Operational audit helpers
├── documentation_records/  # Human-written project notes and reports
├── logs/                   # Output logs and audit exports
├── real data/              # Additional SQLite database copies
├── skills/                 # Local Codex skill assets
├── .planning/              # GSD planning state and codebase maps
├── .codex/                 # Codex agent/tooling files
├── .opencode/              # OpenCode tooling files
├── requirements.txt        # Python dependency manifest
├── .gitignore              # Generated artifact exclusions
└── all_programs.txt        # Generated source dump
```

## Directory Purposes

**`app/`:**
- Purpose: Hold the runtime-facing application layer.
- Contains: `app/app.py` Flask dashboard, `app/stream_engine.py`, `app/real_time_predictor.py`, planner logic in `app/forecast_support.py`, CLI-style modules `app/forecast_routes.py` and `app/compare_external_benchmark.py`.
- Key files: `app/app.py`, `app/stream_engine.py`, `app/forecast_support.py`, `app/real_time_predictor.py`
- Notes: This directory also stores generated artifacts such as `app/route_forecaster.joblib`, `app/route_forecast_training_dataset.csv`, `app/route_forecast_future_dataset.csv`, and `app/route_forecaster_metrics.json`.

**`data/`:**
- Purpose: Own ingestion code and the main SQLite database.
- Contains: `data/real_data_fetcher.py`, `data/fetch_fred_data.py`, `data/import_quotes.py`, `data/shipments.db`
- Key files: `data/real_data_fetcher.py`, `data/fetch_fred_data.py`, `data/import_quotes.py`, `data/shipments.db`
- Notes: Put schema-changing ingestion work here, not in `scripts/`.

**`pipeline/`:**
- Purpose: Coordinate multi-step data flows and build intermediate feature datasets.
- Contains: `pipeline/real_data_pipeline.py`, `pipeline/real_data_feature_engineering.py`, `pipeline/build_train_data.py`, `pipeline/build_forecast_dataset.py`, `pipeline/benchmark_manager.py`
- Key files: `pipeline/real_data_pipeline.py`, `pipeline/build_train_data.py`, `pipeline/real_data_feature_engineering.py`
- Notes: Use this directory for orchestration modules that call lower-level services from `data/`, `app/`, and `ml/`.

**`ml/`:**
- Purpose: Hold model training and evaluation entry points plus benchmark model artifacts.
- Contains: `ml/train_model.py`, `ml/train_route_forecaster.py`, `ml/evaluate_route_forecaster.py`, `ml/model_health_check.py`, joblib artifacts, training profile JSON
- Key files: `ml/train_model.py`, `ml/train_route_forecaster.py`, `ml/evaluate_route_forecaster.py`, `ml/model_health_check.py`
- Notes: Keep model training and offline evaluation logic here. Persist benchmark model artifacts such as `ml/benchmark_model.joblib` and `ml/benchmark_features.joblib` here.

**`scripts/`:**
- Purpose: Provide short command entry points that import `main()` from package modules.
- Contains: wrappers like `scripts/train_route_forecaster.py`, `scripts/forecast_routes.py`, `scripts/import_quotes.py`, `scripts/evaluate_route_forecaster.py`, plus maintenance utilities `scripts/dump_code.py` and `scripts/fix_paths.py`
- Key files: `scripts/train_route_forecaster.py`, `scripts/forecast_routes.py`, `scripts/import_quotes.py`, `scripts/real_data_audit.py`
- Notes: Add a script here only when the underlying logic already lives elsewhere.

**`utils/`:**
- Purpose: Store operational helper modules outside the main runtime path.
- Contains: `utils/real_data_audit.py`
- Key files: `utils/real_data_audit.py`
- Notes: Audit and diagnostic code belongs here when it is not a production runtime dependency.

**`documentation_records/`:**
- Purpose: Keep narrative project documents and historical change notes.
- Contains: markdown reports and text records.
- Key files: `documentation_records/README.md`, `documentation_records/CHANGES_README.md`, `documentation_records/model_optimization_report.md`

**`logs/`:**
- Purpose: Keep generated logs and exported reports.
- Contains: training logs, audit CSVs, code dumps.
- Key files: `logs/real_data_audit_report.csv`, `logs/train_output.txt`, `logs/health.txt`

**`real data/`:**
- Purpose: Hold extra SQLite database files outside the main `data/` directory.
- Contains: `real data/shipments.db`, `real data/engineered_shipments.db`
- Key files: `real data/shipments.db`, `real data/engineered_shipments.db`
- Notes: Treat this as data storage, not as a source-code package despite the directory name.

**`.planning/`:**
- Purpose: Store project planning state and codebase maps used by GSD workflows.
- Contains: `PROJECT.md`, `REQUIREMENTS.md`, `ROADMAP.md`, `STATE.md`, `codebase/*.md`
- Key files: `.planning/PROJECT.md`, `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/STRUCTURE.md`

## Key File Locations

**Entry Points:**
- `app/app.py`: Flask dashboard and API server; starts the live stream engine.
- `pipeline/real_data_pipeline.py`: End-to-end observable data pipeline runner.
- `pipeline/build_forecast_dataset.py`: CLI dataset builder for planner training and future forecast inputs.
- `ml/train_route_forecaster.py`: Planner training entry point.
- `ml/evaluate_route_forecaster.py`: Planner evaluation entry point.
- `ml/train_model.py`: Legacy benchmark model training entry point.
- `data/import_quotes.py`: Quote-history CSV import entry point.
- `app/compare_external_benchmark.py`: External benchmark import and comparison entry point.

**Configuration:**
- `requirements.txt`: Runtime dependency list.
- `.gitignore`: Generated artifact and database exclusions.
- `.planning/PROJECT.md`: Project intent and current work constraints.

**Core Logic:**
- `app/forecast_support.py`: Central route-planning domain module.
- `data/real_data_fetcher.py`: Observable schema and ingestion owner.
- `app/stream_engine.py`: Live tick generation, prediction, and retrain service.
- `app/real_time_predictor.py`: Observable scoring service.
- `pipeline/real_data_feature_engineering.py`: Observable feature engineering.
- `pipeline/build_train_data.py`: Benchmark training dataset assembly.

**Testing:**
- Not detected. There is no dedicated `tests/` directory and no `*.test.py` or `*.spec.py` files in the main source tree.

## Naming Conventions

**Files:**
- Use `snake_case.py` for Python modules, for example `real_data_fetcher.py`, `train_route_forecaster.py`, and `model_health_check.py`.
- Use wrapper scripts that mirror their target module names, for example `scripts/forecast_routes.py` -> `app/forecast_routes.py`.
- Keep generated artifacts beside their consuming modules, for example `ml/benchmark_model.joblib` and `app/route_forecaster.joblib`.

**Directories:**
- Use short lowercase package names by concern: `app`, `data`, `pipeline`, `ml`, `scripts`, `utils`.
- Non-package operational directories are also lowercase with underscores when needed, for example `documentation_records`.

## Where to Add New Code

**New Web/API Feature:**
- Primary code: `app/app.py` for routes and HTTP wiring.
- Supporting service logic: add or extend a helper module in `app/` if the behavior is runtime-facing and reused by multiple routes.

**New Observable Data Source or Schema Extension:**
- Primary code: `data/real_data_fetcher.py` or a new module under `data/`
- Pipeline integration: `pipeline/real_data_pipeline.py`
- Database changes: keep table creation or migration logic near `RealDataFetcher` if it affects the shared observable/planner schema.

**New Planner Training or Forecast Logic:**
- Primary code: `app/forecast_support.py`
- Training/evaluation command surface: `ml/train_route_forecaster.py` or `ml/evaluate_route_forecaster.py`
- CLI wrapper: matching file under `scripts/` only if users need a short command path.

**New Feature Engineering:**
- Observable model features: `pipeline/real_data_feature_engineering.py`
- Benchmark model training features: `pipeline/build_train_data.py`
- Planner training/future forecast features: `app/forecast_support.py`

**New Model Health or Audit Command:**
- Implementation: `utils/` or `ml/` depending on whether the command is operational audit or model-specific validation.
- Wrapper: `scripts/` if it should be operator-friendly.

**Utilities:**
- Shared helpers: prefer adding them near the domain that owns them instead of creating a generic catch-all module. This repo does not have a broad shared helper layer today.

## Organization Patterns

**Wrapper Pattern:**
- `scripts/*.py` usually contain only a `sys.path` shim, one import, and an `if __name__ == "__main__":` block.
- Keep business logic out of these wrappers. Put the real implementation in `app/`, `data/`, `pipeline/`, `ml/`, or `utils/`.

**Path Resolution Pattern:**
- Most modules compute `PROJECT_ROOT` from `__file__` and insert it into `sys.path`.
- New top-level executable modules should follow the same pattern for consistency with existing imports.

**Artifact Placement Pattern:**
- Runtime planner artifacts live in `app/`.
- Benchmark model artifacts live in `ml/`.
- Persistent tabular state lives in SQLite under `data/`.
- Logs and exported reports live in `logs/`.

## Special Directories

**`__pycache__/`:**
- Purpose: Python bytecode cache.
- Generated: Yes
- Committed: No

**`logs/`:**
- Purpose: Generated operational output and training logs.
- Generated: Yes
- Committed: Mixed; files are present in the working tree, but the directory is ignored in `.gitignore`.

**`data/` database files:**
- Purpose: Shared application state.
- Generated: Yes
- Committed: No according to `.gitignore` (`data/*.db`).

**`real data/` database files:**
- Purpose: Additional database copies.
- Generated: Yes
- Committed: No according to `.gitignore` (`real data/*.db`).

**`ml/` joblib files:**
- Purpose: Serialized benchmark model artifacts.
- Generated: Yes
- Committed: No according to `.gitignore` (`ml/*.joblib`).

**`app/` planner artifacts:**
- Purpose: Serialized planner bundle and CSV snapshots.
- Generated: Yes
- Committed: No according to `.gitignore` (`app/*.joblib`, `app/*.csv`, `app/route_forecaster_metrics.json`).

**`.planning/`:**
- Purpose: Planning metadata and generated codebase documentation.
- Generated: Yes
- Committed: Yes; this directory is part of the workflow state.

**`.codex/` and `.opencode/`:**
- Purpose: Local AI tooling and workflow scaffolding.
- Generated: Tool-managed
- Committed: Yes in this repository snapshot.

---

*Structure analysis: 2026-03-26*
