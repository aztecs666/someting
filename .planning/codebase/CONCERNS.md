# Codebase Concerns

## Tech Debt

- **Code Duplication:** `scripts/` contains thin wrappers that mirror modules in `app/`, `ml/`, `pipeline/`, `data/`, and `utils/`. Each script (e.g., `scripts/forecast_routes.py`) just imports and calls `main()` from the real module (e.g., `app/forecast_routes.py`). This creates 8+ duplicate entry points that must stay in sync.
- **Hardcoded Route Distances:** `pipeline/build_train_data.py:80-89` — Nautical mile distances are hardcoded in a dict literal. Adding new routes requires code changes.
- **Hardcoded DB Path:** `pipeline/build_train_data.py:23` — `DB_PATH` is constructed relative to file location. Fragile if project structure changes.
- **Hardcoded Peak Season:** `pipeline/build_train_data.py:105` — Peak season months `[9, 10, 11, 12, 1, 2]` are hardcoded, not configurable.
- **Missing Import:** `pipeline/build_train_data.py:34` — `warnings.warn()` is called but `warnings` module is **never imported**. This will crash at runtime if triggered.
- **No TODO/FIXME/HACK comments found** — The codebase is clean of explicit debt markers.

## Known Issues

- **No Private Quote History:** Per `CHANGES_README.md:201` — The model is trained on external benchmark data (Compass/Xeneta), not actual commercial quotes. Outputs are planning proxies only.
- **Forward Forecasts Unverifiable:** `CHANGES_README.md:202` — Public benchmark data only reaches 2026-03-13, so late March/April forecasts cannot be validated yet.
- **Weather Horizon Gap:** `CHANGES_README.md:203` — Free weather data covers only 16 days; forecasts for days 17-20 include a horizon-gap penalty.
- **Legacy Dashboard:** `app/app.py` is marked as a legacy sandbox UI per documentation. May mislead users about forecast accuracy.

## Security Concerns

- **SQLite Database in Repo:** `data/shipments.db` (8MB) is tracked in git. Contains potentially sensitive shipping data. Consider adding to `.gitignore` and using a migration script instead.
- **No Input Validation:** API endpoints in `app/` lack input sanitization for route names, dates, and parameters.
- **No Authentication:** The Flask app (`app/app.py`) has no auth layer. All endpoints are publicly accessible.

## Performance

- **Sequential Route Processing:** `pipeline/build_train_data.py:119` — Training samples are built by iterating routes one-by-one in Python. Could be vectorized with pandas.
- **No Caching:** Repeated DB queries for the same benchmark data. No caching layer between pipeline stages.
- **Full DB Load:** `pipeline/build_train_data.py:72` — Entire benchmark history is loaded into memory. Could be problematic with larger datasets.
- **No Connection Pooling:** SQLite connections are opened/closed per function call. No connection reuse.

## Fragile Areas

- **Route Distance Fallback:** `pipeline/build_train_data.py:93` — Unknown routes silently default to 5000nm. Could produce misleading predictions without warning.
- **Temp File Leftover:** `temp_output.txt` is in the repo root — appears to be accidental output.
- **Dual DB Paths:** `DB_PATH` in `build_train_data.py` points to `data/shipments.db`, but `.gitignore` also references `real data/*.db` and `data/*.db`. Inconsistent DB location expectations.
- **Skill Config:** `skills/senior-data-scientist/.skillfish.json` is committed — may contain environment-specific settings.

## Documentation Gaps

- **No API Documentation:** Flask routes in `app/app.py` and `app/forecast_routes.py` have no Swagger/OpenAPI spec or endpoint documentation.
- **No Setup Guide:** `requirements.txt` lists dependencies but no Python version requirement, no virtual env instructions, no data setup steps beyond the CHANGES_README.
- **No Architecture Decision Records:** Why XGBoost? Why residual-blend? These decisions exist in `model_optimization_report.md` but aren't linked from the main README.
- **Missing Type Hints:** Most functions lack type annotations. `get_features()` returns a list but no type hint.
- **No Contribution Guide:** No `.github/CONTRIBUTING.md` or development workflow docs.

## Recommendations (Priority Order)

1. **CRITICAL:** Add `import warnings` to `pipeline/build_train_data.py` — will crash at runtime
2. **HIGH:** Add `data/*.db` to `.gitignore` and remove `shipments.db` from tracking
3. **HIGH:** Add input validation to Flask endpoints
4. **MEDIUM:** Extract hardcoded constants (distances, peak season) to config file
5. **MEDIUM:** Add type hints across codebase for better IDE support
6. **MEDIUM:** Add API documentation (Swagger or simple endpoint list)
7. **LOW:** Consolidate `scripts/` wrappers into a single CLI entry point (argparse/click)
8. **LOW:** Remove `temp_output.txt` from repo
