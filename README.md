# RECIST Clinical QC

A local web workspace and Python CLI for lesion CSV quality checks, unconfirmed RECIST 1.1 timepoint response review, and comparison against reported responses. Python 3.11+; no third-party runtime dependencies, account, database, or API key.

## Windows: start here

1. Extract the downloaded project ZIP. Do not run from inside the ZIP.
2. Open the extracted folder containing this README.
3. Double-click **start_windows.bat** (Windows may hide the `.bat` extension).
4. The launcher runs the automated tests, verifies the built-in expected results, and opens your browser on an available local port. Keep the command window open. Close it or press Ctrl+C to stop.
5. Leave **RECIST responses and reported-response checks** selected and click **Run selected example**.
6. Click **Run all built-in tests** to see each expected-output check. Try another example or upload your own CSV. Download the complete JSON, findings CSVs, response CSV, test evidence, or print/save the review as PDF.

If Python is missing, install Python 3.11 or newer from python.org. If the launcher shows failures, keep the error text; it deliberately does not start when its checks fail. The launcher selects a fresh available port so an older running copy is not mistaken for the updated app. Never replace a running app's folder; stop it before extracting an update into a new folder.

On macOS/Linux, from the extracted project folder run `python3 launch.py`. Direct server startup also works:

```sh
python -m recist_qc serve
```

This development server binds to loopback. Use synthetic or de-identified data. Uploads up to 2 MiB are processed in memory; the app does not save files or log requests. It has no authentication and is not designed for public hosting. Locally downloaded reports remain on your computer.

## What is included

- Seven built-in examples: one complete response/comparison example plus six data quality cases. No separate sample download is required to try them.
- Data checks for schema, required values, measurements, dates, duplicates, target-size and target-count criteria, and longitudinal attribute changes.
- Target and overall CR/PR/SD/PD/NE calculations, baseline/nadir measurements, percentage changes, and explanations.
- QC comparison of an optional reported response against the calculated overall response.
- Fifteen built-in expected-output checks, visible in the app and downloadable as test evidence.
- Automated unit, CLI, and HTTP tests, run by the launcher.

## CSV contract

One row represents a lesion at a patient visit. Use the sample from the app as a template. All eight measurement columns and their values are required. Identifiers are case-sensitive; visit names, organ names, lesion type and target designation are compared case-insensitively. Use consistent organ labels, including a common `lymph_nodes` label for nodal targets.

| Column | Meaning |
| --- | --- |
| patient_id | De-identified patient identifier |
| visit | `baseline` for initial assessment; consistent names for follow-ups |
| assessment_date | Calendar date, exactly `YYYY-MM-DD` |
| lesion_id | Stable identifier across visits |
| organ | Consistent organ label |
| lesion_type | `nodal` or `non_nodal` |
| is_target | `yes` or `no`; retain baseline designation across visits |
| diameter_mm | Finite, nonnegative number; short axis for nodes and longest diameter for non-nodal lesions |

Response review uses three additional columns. They may be blank at baseline. Repeat the same assessment flags on **every row** at each follow-up:

| Column | Accepted values |
| --- | --- |
| new_lesions | `yes`, `no`, `unknown`. `yes` means unequivocal new lesions, based on review. |
| non_target_response | `CR`, `NON_CR_NON_PD`, `PD`, `NE`, `NOT_APPLICABLE`. PD means unequivocal non-target progression; NOT_APPLICABLE means no non-target disease. |
| reported_response | Optional `CR`, `PR`, `SD`, `PD`, `NE` for comparison with the calculated overall response. |

[Complete response sample](examples/response_review.csv) includes eight synthetic patients and deliberately incorrect or unverifiable reported responses. [Additional data examples](examples/test_data/README.md) have documented expected results. Missing flags are never assumed to mean absence of disease.

## Rules and limits

Data errors include missing or duplicate columns, empty required values, malformed CSV/rows, invalid dates, invalid categories, invalid measurements and duplicate patient/visit/lesion records. Data warnings include changing target designation/type/organ, differing dates within a visit, baseline targets below 10 mm non-nodal or 15 mm nodal, more than five baseline targets per patient and more than two per organ. Size findings require review because measurability also depends on modality, slice thickness, prior treatment and lesion characteristics. Zero follow-up measurements are allowed.

Response review is held for **the entire uploaded file** until data QC errors and warnings are resolved. The response engine requires a measurable baseline target set and exactly the same target IDs at every follow-up. A missing lesion is not assumed to have disappeared. Visits are ordered by assessment date. Ambiguous dates or an incomplete earlier target assessment prevent establishing the nadir and yield NE.

- Target CR: non-nodal targets all measure zero and each target node is below 10 mm short axis. Residual nodal measurements remain in the sum.
- Target PD: at least 20% increase **and** at least 5 mm absolute increase from the prior nadir, including baseline. If nadir is zero the percentage is undefined and the 5 mm absolute threshold is still required.
- Target PR: at least 30% decrease from baseline without target PD.
- Target SD: neither CR, PR nor PD.
- Overall PD: valid positive evidence of target progression, unequivocal non-target progression, or unequivocal new lesions.
- Overall CR requires target CR, non-target CR (or no non-target disease), and no new lesions. Persistent non-target disease with target CR gives PR.
- Missing or inconsistent visit-level flags yield NE. This conservative workflow also yields NE for unknown new-lesion status or NE non-target status unless valid progression evidence is present. It does not implement RECIST allowances for all partially evaluated non-target combinations; review those cases clinically.

Reported responses are optional. A mismatch is flagged; an NE calculation cannot verify a reported evaluable response. Agreement is agreement with the implemented rules, not independent proof of clinical correctness.

**This is a development review aid, not a clinically validated system.** Calculations are unconfirmed timepoint assessments. This version does not determine best overall response, confirmed response, protocol-specific SD duration/confirmation windows, non-target-only disease response, imaging adequacy, non-target progression from measurements, new-lesion equivocality, iRECIST, or clinical endpoints. Measurements and disease flags must already have been reviewed appropriately. Synthetic regression tests are software checks, not clinical validation. Passing data QC does not establish RECIST compliance.

Reference: Eisenhauer et al., European Journal of Cancer 45 (2009), 228–247, doi:10.1016/j.ejca.2008.10.026. Protocol-specific validation remains necessary before clinical use.

## CLI

```sh
python -m recist_qc check examples/lesions.csv
python -m recist_qc check examples/lesions_with_issues.csv --format csv --output findings.csv
python -m recist_qc responses examples/response_review.csv --output response-report.json
python -m unittest discover -s tests -v
```

`check` exits 0 with no findings, 1 when findings need review, 2 for file/encoding failures. `responses` exits 1 for blocked calculations, NE assessments or response QC findings; 0 otherwise; 2 for file/encoding failures. CSV data finding rows count logical CSV records, including the header; quoted multiline records can span physical lines.

Optional editable installation: create a virtual environment and run `python -m pip install -e .` within it. This downloads setuptools as an isolated build dependency; runtime is standard library only. The `recist-qc` command then mirrors `python -m recist_qc`.

## HTTP API

`GET /health`; `GET /api/examples`; `GET /api/examples/{id}.csv`; `GET /api/self-test`. Send raw UTF-8 CSV bytes to `POST /api/check` (data only), `/api/responses` (response review), or `/api/analyze` (combined). Invalid data findings are reported in a successful HTTP response; unreadable bodies/encoding or size violations use 4xx errors. An HTTP 200 does not mean clinical QC passed.
