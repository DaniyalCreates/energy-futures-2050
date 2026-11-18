# Decisions

Format: ID · date · decision · reason · status.

| ID | Date | Decision | Reason | Status |
| --- | --- | --- | --- | --- |
| D-001 | 2026-11-18 | Working title drops "Digital Twin"; it stays a long-term roadmap goal | An aggregated national model with no live feedback loop is not a digital twin | Approved |
| D-002 | 2026-11-18 | 6-arm factorial experiment (A, B, B+, C-, C, Oracle) instead of 3-way A/B/C | Separates the effect of the probabilistic forecast from the risk-aware decision method; the Oracle arm bounds the value forecasting could add | Approved |
| D-003 | 2026-11-18 | MVP scope: GB aggregate, day-ahead half-hourly; PyPSA, network/regional modelling and deep learning deferred to Phase 2 | One researcher, ~3 h/day; the core loop first | Approved |
| D-004 | 2026-11-18 | Environment: `uv` with Python 3.12, dependencies pinned in `uv.lock` (universal lock, includes macOS arm64 wheels) | Reproducible; simpler than conda on Apple Silicon | Approved |
| D-005 | 2026-11-18 | Batch 1 dependencies only: numpy, pandas, pyarrow, requests, pyyaml (+ pytest dev). scikit-learn, LightGBM, SciPy, Plotly, Streamlit added in the batch that needs them | Install only what the current stage uses | Approved |
| D-006 | 2026-11-18 | pandas 3.x accepted (resolved 3.1.1) | Current release; note copy-on-write and the default string dtype when writing pipeline code | Recorded |
| D-007 | 2026-11-18 | Data, outputs and model artefacts are git-ignored; provenance is recorded in docs and a raw-data manifest instead | Keeps the repo small and free of licensed bulk data; reproducible from source | Approved |
| D-008 | 2026-11-18 | NESO's published day-ahead demand forecast is the operational benchmark in Step 26 | The strongest available real-world comparison | Approved |
| D-009 | 2026-11-18 | Weather from ERA5 reanalysis is labelled "perfect-weather" information; NESO benchmark comparisons use a realistic-weather setting (lagged, or archived forecasts) | Reanalysis would give our model knowledge NESO did not have at forecast time | Approved (Batch 2) |
| D-010 | 2026-11-18 | Primary target = underlying demand (ND + estimated embedded solar + embedded wind); ND kept as an alternative target | ND falls as rooftop solar grows, which is not a real drop in demand; the cost is inheriting NESO's estimation error | Provisional: confirm after inspecting the data (Step 13) |
| D-011 | 2026-11-18 | Historical window 2009–2025 | The data format is consistent from 2009 and embedded solar was negligible before then; COVID-19 and the 2022 price shock are handled by testing training windows later, not by dropping years | Approved (Batch 2) |
| D-012 | 2026-11-18 | Six-location equal-weight GB weather mean; population weighting deferred | Weights must come from a verified ONS source, not guesses | Approved (Batch 2) |
| D-013 | 2026-11-18 | Downloads run on Dani's Mac (`uv run python -m energy_futures.pipeline download`); Claude's sandboxes can't reach NESO or Open-Meteo (blocked by the egress allowlist) | Avoids changing account network settings; one command, reproducible | Approved (Batch 2) |
