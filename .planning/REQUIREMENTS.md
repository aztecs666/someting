# Requirements: Real Data Planner

**Defined:** 2026-03-26
**Core Value:** The planner must produce defensible, clearly-labeled forecasts from the repo's real data sources without failing on obvious runtime issues.

## v1 Requirements

### Planning Workflow

- [x] **PLAN-01**: The repository includes the .planning project files referenced by AGENTS.md
- [x] **PLAN-02**: Current work status is tracked in .planning/STATE.md
- [x] **PLAN-03**: Repair work is executed as atomic, auditable commits

### Runtime Reliability

- [x] **RUN-01**: Training dataset construction runs without immediate import or name-resolution failures
- [x] **RUN-02**: Core CLI and module entry points import without crashing under the configured environment
- [x] **RUN-03**: Validation steps exist for each repaired defect

### Data And Forecast Integrity

- [x] **DATA-01**: Forecasting code uses real-data-backed paths and labels consistently
- [x] **DATA-02**: Known fragile defaults and silent failures are documented or corrected
- [x] **DATA-03**: The repo makes its current planning-proxy limitations explicit

## v2 Requirements

### Hardening

- [ ] **HARD-01**: Add automated tests for pipeline, training, and forecast routes
- [ ] **HARD-02**: Add API input validation and auth for exposed Flask endpoints
- [ ] **HARD-03**: Externalize hardcoded route and seasonality configuration

## Out of Scope

| Feature | Reason |
|---------|--------|
| Major architecture rewrite | Current task is defect analysis and repair, not redesign |
| Net-new dashboard experience | Existing dashboard is documented as legacy and non-core |
| CI/CD rollout | Valuable, but secondary to restoring a working local baseline |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| PLAN-01 | Phase 1 | Complete |
| PLAN-02 | Phase 1 | Complete |
| PLAN-03 | Phase 1 | Complete |
| RUN-01 | Phase 2 | Complete |
| RUN-02 | Phase 2 | Complete |
| RUN-03 | Phase 2 | Complete |
| DATA-01 | Phase 3 | Complete |
| DATA-02 | Phase 3 | Complete |
| DATA-03 | Phase 3 | Complete |

**Coverage:**
- v1 requirements: 9 total
- Mapped to phases: 9
- Completed: 9
- Unmapped: 0

---
*Requirements defined: 2026-03-26*
*Last updated: 2026-04-03 after Phase 3 and Phase 4 completion*