# Roadmap: Real Data Planner

## Overview

This roadmap restores the missing project-planning layer first, then works through runtime breakages, data/forecast integrity concerns, and finally repo hygiene that materially affects reliable operation.

## Phases

- [x] **Phase 1: Restore GSD State** - Recreate required planning files and establish the repair queue
- [x] **Phase 2: Fix Runtime Breakages** - Resolve concrete import, execution, and command failures
- [x] **Phase 3: Correct Data And Forecast Integrity Issues** - Align labels, paths, and planner behavior with real-data expectations
- [x] **Phase 4: Tighten Repo Hygiene** - Address high-signal workflow and maintainability issues that block safe iteration

## Phase Details

### Phase 1: Restore GSD State
**Goal**: The repository has the planning artifacts required by AGENTS.md, and current repair work is tracked.
**Depends on**: Nothing (first phase)
**Requirements**: PLAN-01, PLAN-02, PLAN-03
**Status**: Complete (2026-03-26)

### Phase 2: Fix Runtime Breakages
**Goal**: Core modules and scripts stop failing on obvious runtime defects.
**Depends on**: Phase 1
**Requirements**: RUN-01, RUN-02, RUN-03
**Status**: Complete (2026-03-26)

### Phase 3: Correct Data And Forecast Integrity Issues
**Goal**: Planner behavior and documentation reflect real-data usage and current limitations accurately.
**Depends on**: Phase 2
**Requirements**: DATA-01, DATA-02, DATA-03
**Status**: Complete (2026-04-03)

### Phase 4: Tighten Repo Hygiene
**Goal**: The repository is easier to operate safely after the core fixes land.
**Depends on**: Phase 3
**Requirements**: PLAN-03
**Status**: Complete (2026-04-03)

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Restore GSD State | 2/2 | Complete | 2026-03-26 |
| 2. Fix Runtime Breakages | 3/3 | Complete | 2026-03-26 |
| 3. Correct Data And Forecast Integrity Issues | 6/2 | Complete | 2026-04-03 |
| 4. Tighten Repo Hygiene | 2/2 | Complete | 2026-04-03 |