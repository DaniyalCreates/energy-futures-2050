# Project status — Energy Futures 2050

_Last updated: 2026-11-18_

## 1. Current position
- **Phase 1 / Batch 1 (Foundation)**, Steps 1–8: files are in `~/Desktop/Energy Futures 2050` and the tests pass in Claude's sandbox on the Mac. **Two items remain before Batch 1 is complete:** (a) Dani runs `uv sync && uv run pytest` in the macOS terminal; (b) done: first commit 6eabf6d.

## 2. Completed tasks and evidence
| Step | Task | Evidence |
| --- | --- | --- |
| 1 | Objectives confirmed against the project brief and the assessment doc | Assessment doc in the Claude Project; DECISIONS D-001 to D-008 |
| 4 | Modular structure created | `tests/test_foundation.py::test_expected_structure_exists` passes |
| 5–6 | `uv` environment, Python 3.12.3, essential packages only | `uv lock` resolved 18 packages; lock includes macOS arm64 wheels |
| 7 | `.gitignore` | 11 ignore-rule tests pass (secrets, data, `.venv`, models, outputs) |
| 8 | Git initialised, README written | `git init -b main` |
| 2–3 | Folder check and creation on the Mac | Dani created the folder; it was confirmed empty before the files were copied in (2026-11-18) |

## 3. Files created
README.md, pyproject.toml, uv.lock, .python-version, .gitignore, .env.example, PROJECT_STATUS.md, DECISIONS.md, EXPERIMENT_LOG.md, CHANGELOG.md, tests/test_foundation.py, src/energy_futures/** (empty package modules), .gitkeep placeholders.

## 4. Dataset provenance
None downloaded yet. Planned sources are listed in README.md; details come in Batch 2 (`docs/data_dictionary.md`).

## 5. Experiments and results
None yet.

## 6. Tests
`uv run pytest`: 13 passed in the cloud workspace, on a fresh clone, and in Claude's Linux sandbox on the Mac with `uv sync --locked` (2026-11-18). Native macOS run: pending (Dani).

## 7. Problems and open questions
- Git identity set for this repo only (Daniyal Tariq, personal Gmail). Commits will show this email publicly if the repo is made public.
- Claude's shell on the Mac is a Linux sandbox. The macOS environment has to be built by Dani with `brew install uv` then `uv sync`. `.venv` is never committed.

## 8. Approved decisions
See DECISIONS.md (D-001 to D-008).

## 9. Next three tasks
1. Dani: `cd ~/Desktop/"Energy Futures 2050" && uv sync && uv run pytest` (uv is already installed).
2. Create a private GitHub repo (DaniyalCreates/energy-futures-2050) when Dani approves publishing.
3. Batch 2, Step 9: audit the NESO historic demand fields → `docs/data_dictionary.md`.
