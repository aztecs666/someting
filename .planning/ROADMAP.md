# Roadmap: Real Data Planner

## Overview

This roadmap restores the missing project-planning layer first, then works through runtime breakages, data/forecast integrity concerns, and finally repo hygiene that materially affects reliable operation.

## Phases

- [ ] **Phase 1: Restore GSD State** - Recreate required planning files and establish the repair queue
- [ ] **Phase 2: Fix Runtime Breakages** - Resolve concrete import, execution, and command failures
- [ ] **Phase 3: Correct Data And Forecast Integrity Issues** - Align labels, paths, and planner behavior with real-data expectations
- [ ] **Phase 4: Tighten Repo Hygiene** - Address high-signal workflow and maintainability issues that block safe iteration

## Phase Details

### Phase 1: Restore GSD State
**Goal**: The repository has the planning artifacts required by `AGENTS.md`, and current repair work is tracked.
**Depends on**: Nothing (first phase)
**Requirements**: PLAN-01, PLAN-02, PLAN-03
**Success Criteria** (what must be TRUE):
  1. `.planning/PROJECT.md`, `REQUIREMENTS.md`, `ROADMAP.md`, and `STATE.md` exist
  2. The current audit and next action are recorded in project state
  3. A first atomic commit captures the restored planning baseline
**Plans**: 2 plans

Plans:
- [ ] 01-01: Create missing GSD project files from local templates and current repo context
- [ ] 01-02: Record initial defect queue and commit the planning baseline

### Phase 2: Fix Runtime Breakages
**Goal**: Core modules and scripts stop failing on obvious runtime defects.
**Depends on**: Phase 1
**Requirements**: RUN-01, RUN-02, RUN-03
**Success Criteria** (what must be TRUE):
  1. Confirmed runtime defects are fixed one at a time
  2. Each fix has a corresponding validation command or smoke test
  3. Each logical repair is committed separately with a detailed message
**Plans**: 3 plans

Plans:
- [ ] 02-01: Run import and smoke checks to build an execution-backed issue list
- [ ] 02-02: Repair immediate code failures blocking dataset or app workflows
- [ ] 02-03: Verify corrected commands and update state after each fix

### Phase 3: Correct Data And Forecast Integrity Issues
**Goal**: Planner behavior and documentation reflect real-data usage and current limitations accurately.
**Depends on**: Phase 2
**Requirements**: DATA-01, DATA-02, DATA-03
**Success Criteria** (what must be TRUE):
  1. Real-data and benchmark-proxy modes are labeled consistently
  2. Fragile defaults or misleading behaviors identified in the audit are reduced or documented
  3. User-facing outputs do not overstate what the data supports
**Plans**: 2 plans

Plans:
- [ ] 03-01: Inspect forecast/training paths for real-data consistency gaps
- [ ] 03-02: Repair or document the highest-risk integrity issues

### Phase 4: Tighten Repo Hygiene
**Goal**: The repository is easier to operate safely after the core fixes land.
**Depends on**: Phase 3
**Requirements**: PLAN-03
**Success Criteria** (what must be TRUE):
  1. High-signal workflow clutter or misleading artifacts are addressed
  2. The final state reflects completed work and any remaining blockers
  3. The repair series is left in a reviewable git history
**Plans**: 2 plans

Plans:
- [ ] 04-01: Address the most important hygiene issues uncovered during repair work
- [ ] 04-02: Final verification, state update, and close-out

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Restore GSD State | 0/2 | In progress | - |
| 2. Fix Runtime Breakages | 0/3 | Not started | - |
| 3. Correct Data And Forecast Integrity Issues | 0/2 | Not started | - |
| 4. Tighten Repo Hygiene | 0/2 | Not started | - |
