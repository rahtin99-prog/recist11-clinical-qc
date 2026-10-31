# Synthetic test CSVs

All identifiers and measurements are invented. Upload one CSV at a time in the web app.

| File | Rows | Errors | Warnings |
| --- | ---: | ---: | ---: |
| [01_clean.csv](01_clean.csv) | 4 | 0 | 0 |
| [02_invalid_values.csv](02_invalid_values.csv) | 6 | 6 | 0 |
| [03_too_many_targets.csv](03_too_many_targets.csv) | 6 | 0 | 2 |
| [04_changes_across_visits.csv](04_changes_across_visits.csv) | 3 | 0 | 2 |
| [05_small_baseline_targets.csv](05_small_baseline_targets.csv) | 2 | 0 | 2 |
| [06_duplicate_records.csv](06_duplicate_records.csv) | 2 | 1 | 0 |

See expected_reports.json for the exact expected findings.

01 is a passing example, including zero follow-up measurement and a shrinking node. 02 tests invalid measurements, an invalid date, invalid categories and a missing organ. 03 exceeds total and per-organ target limits. 04 changes lesion organ and has inconsistent visit dates. 05 has small baseline targets. 06 repeats a lesion record.
