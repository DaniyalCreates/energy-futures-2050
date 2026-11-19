# Research change log (improvement phase)

_Every change after the audit (commit 5db4552, verdict B) is recorded here: goal, files, commands, tests, old vs new results, failures, remaining uncertainty._

## Ground rules
- Baseline: tag `v1-audit-baseline` = commit `5db4552`. Return to it with `git checkout v1-audit-baseline`.
- Work happens on branch `improve/phase-b`; `main` stays as audited until Dani approves a merge.
- Original results are frozen in `outputs_archive/v1_5db4552/` with `SHA256SUMS`; new results go to new versioned folders, never over old ones.
- 2026 data (Jan-Oct) is reserved for ONE pre-declared confirmation run, after the improved calibration is frozen. Disclosure: the NESO day-ahead benchmark file already on disk contains 2026 rows; they were loaded in Batch 4 but never used for modelling, and two rows (18 Nov 2026) were printed once while checking the file format.
- Pre-registration seal: **laptop only** (Dani's choice). Write-ups must state that the protocol's timing cannot be verified by outsiders.

## CS-0 · 19 Nov 2026 · Safety baseline
- **Goal:** make every later change reversible and keep original results provably unchanged.
- **Commands:** `git tag -a v1-audit-baseline 5db4552`; `cp -an outputs` and `data/processed` → `outputs_archive/v1_5db4552/`; `sha256sum` list → `SHA256SUMS` (45 files, 37 MB); `git switch -c improve/phase-b`.
- **Note:** the temporary `outputs/transfer/` bundles were removed from the archive *copy* after copying (originals untouched); results files are all archived.
- **Check:** archived dataset fingerprint `66a4d9a0dc66754f` = audited dataset.
- **Files changed:** `.gitignore` (ignore `outputs_archive/`), this log.
