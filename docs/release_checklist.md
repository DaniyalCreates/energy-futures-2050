# Public release checklist (Step 50)

_Status: **prepared, not published.** Nothing has been pushed or deployed. Each item marked **DECISION** needs Dani's explicit approval._

## Completed checks (19 Nov 2026)

| Check | Result |
| --- | --- |
| Secrets scan (working tree + full git history: API keys, tokens, private keys, passwords) | None found |
| Data or model files in history (`data/`, `outputs/`, `.parquet`, `.pkl`, `.env`) | None (only `.gitkeep` placeholders) |
| Absolute local paths in tracked files | None |
| Repository size | 89 tracked files, 1.5 MB |
| Dependency vulnerabilities (`pip-audit`, 156 pinned packages) | No known vulnerabilities |
| Lockfile consistent (`uv lock --check`) | Yes |
| Clean-clone test run without data (what CI will see) | 58 passed, 11 data-dependent skipped |
| Raw → processed data rebuild | Identical (298,032 × 46) |
| Fresh-clone experiment rerun | See `docs/reproducibility_audit.md` |

## Decisions needed before publishing

1. **DECISION: code licence.** Recommended: **MIT** (permissive, standard for portfolio and research code; employers and partners can read and reuse it). Alternative: Apache-2.0 (adds a patent grant). The licence covers code only; data stays under its own licences (below).
2. **DECISION: commit email.** All 14 commits use `tariqdaniyal048@gmail.com`, which becomes public with the repo. Options:
   - (a) keep it;
   - (b) switch future commits to the GitHub noreply address;
   - (c) also rewrite existing history to the noreply address. This rewrites every commit hash, so it must happen *before* the first push and needs approval.
3. **DECISION: repository name and visibility.** Suggested: `DaniyalCreates/energy-futures-2050`, created **private** first, made public after you have reviewed the README and reports.
4. **DECISION: dashboard deployment.** Streamlit Community Cloud can host the app for free, but the app needs result files that are deliberately not in git (about 40 MB). Options:
   - (a) local-only demo (no action);
   - (b) attach a results snapshot to a GitHub Release, with the app downloading it on start (small code change);
   - (c) commit a slimmed results snapshot (~5 MB) to a `results/` folder.

   Option (b) keeps the repo clean. Any of these redistributes NESO-derived results, which the NESO Open Data Licence allows with attribution.

## Data licences and attribution (must stay in README)

- NESO data (historic demand, day-ahead forecast performance, FES 2025): NESO Open Data Licence. Attribution: "Supported by National Energy SO Open Data".
- Open-Meteo (ERA5 historical weather and archived forecasts): CC BY 4.0, "Weather data by Open-Meteo.com". **The free API tier is non-commercial.** A commercial or partner deployment needs an Open-Meteo licence or raw ERA5 from Copernicus.
- Raw data is not redistributed; users download it with the pipeline.

## Deployment instructions

**Local (works today):**

```bash
brew install uv libomp            # macOS; on Linux: install uv only
git clone <repo-url> && cd energy-futures-2050
uv sync
uv run python -m energy_futures.pipeline all          # ~10 min: NESO + weather download and build
uv run python -m energy_futures.ingest.benchmarks     # NESO day-ahead forecasts + archived weather forecasts
uv run python -m energy_futures.ingest.fes            # FES 2025 tables
uv run python -m energy_futures.experiments.baselines
uv run python -m energy_futures.experiments.advanced validation
uv run python -m energy_futures.experiments.advanced test
uv run python -m energy_futures.experiments.advanced_report
uv run python -m energy_futures.experiments.scenarios
uv run python -m energy_futures.experiments.optimisation historical
uv run python -m energy_futures.experiments.optimisation future
uv run python -m energy_futures.experiments.optimisation report
uv run streamlit run dashboard/app.py
```

The full experiment rerun takes about 45 minutes on a laptop.

**Streamlit Community Cloud (only after decision 4):** connect the GitHub repo at share.streamlit.io, set the entry point to `dashboard/app.py` and Python to 3.12. Results must be available via option 4(b) or 4(c).

## Before making the repo public

- [ ] Decisions 1–4 made
- [ ] README read and approved by Dani
- [ ] `docs/technical_report.md` and `docs/ktp_case_study.md` read and approved
- [ ] LICENSE file added
- [ ] CI run green on GitHub (first push to the private repo)
- [ ] Repository description and topics set (e.g. `energy-forecasting`, `conformal-prediction`, `optimisation`, `uk-energy`)
