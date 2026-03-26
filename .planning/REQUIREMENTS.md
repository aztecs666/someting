# Requirements: Real Data Planner

**Defined:** 2026-03-26
**Core Value:** The planner must produce defensible, clearly-labeled forecasts from the repo's real data sources without failing on obvious runtime issues.

## v1 Requirements

### Planning Workflow

- [ ] **PLAN-01**: The repository includes the `.planning` project files referenced by `AGENTS.md`
- [ ] **PLAN-02**: Current work status is tracked in `.planning/STATE.md`
- [ ] **PLAN-03**: Repair work is executed as atomic, auditable commits

### Runtime Reliability

- [ ] **RUN-01**: Training dataset construction runs without immediate import or name-resolution failures
- [ ] **RUN-02**: Core CLI and module entry points import without crashing under the configured environment
- [ ] **RUN-03**: Validation steps exist for each repaired defect

### Data And Forecast Integrity

- [ ] **DATA-01**: Forecasting code uses real-data-backed paths and labels consistently
- [ ] **DATA-02**: Known fragile defaults and silent failures are documented or corrected
- [ ] **DATA-03**: The repo makes its current planning-proxy limitations explicit

## v2 Requirements

### Hardening

- **HARD-01**: Add automated tests for pipeline, training, and forecast routes
- **HARD-02**: Add API input validation and auth for exposed Flask endpoints
- **HARD-03**: Externalize hardcoded route and seasonality configuration

## Out of Scope

| Feature | Reason |
|---------|--------|
| Major architecture rewrite | Current task is defect analysis and repair, not redesign |
| Net-new dashboard experience | Existing dashboard is documented as legacy and non-core |
| CI/CD rollout | Valuable, but secondary to restoring a working local baseline |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| PLAN-01 | Phase 1 | In Progress |
| PLAN-02 | Phase 1 | In Progress |
| PLAN-03 | Phase 1 | Pending |
| RUN-01 | Phase 2 | Pending |
| RUN-02 | Phase 2 | Pending |
| RUN-03 | Phase 2 | Pending |
| DATA-01 | Phase 3 | Pending |
| DATA-02 | Phase 3 | Pending |
| DATA-03 | Phase 3 | Pending |

**Coverage:**
- v1 requirements: 9 total
- Mapped to phases: 9
- Unmapped: 0

---
*Requirements defined: 2026-03-26*
*Last updated: 2026-03-26 after initial GSD restoration*
