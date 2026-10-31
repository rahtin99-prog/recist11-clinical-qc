# RECIST 1.1 Clinical QC

A Python CSV quality-checking tool and a local web app sharing one engine. Uses only the Python standard library at runtime. Python 3.11 or newer is required.

## Run

From this repository:

```sh
python -m recist_qc check examples/lesions.csv
python -m recist_qc check examples/lesions.csv --format csv --output /tmp/qc-findings.csv
python -m recist_qc serve
```

The local web app listens on port 8000, on the loopback interface. Upload a UTF-8 CSV up to 2 MiB to see findings and download a JSON report. Uploads are processed in memory, with no application file storage or request logging. This is a development server without authentication; use synthetic or de-identified data and keep it bound to loopback.

Optional installation provides the equivalent `recist-qc` command:

```sh
python -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/recist-qc check examples/lesions.csv
```

Editable installation downloads setuptools >=68 as an isolated build dependency. Direct module execution needs no installation or third-party packages.

## CSV contract

One row represents a lesion at a patient visit. All eight columns and all their values are required; additional columns are ignored. Identifiers are case-sensitive. Visit names, organ names, lesion type, and target designation are compared case-insensitively. Use consistent organ naming, including a common `lymph_nodes` organ label for nodal targets.

| Column | Meaning |
| --- | --- |
| patient_id | De-identified patient identifier |
| visit | `baseline` for initial assessment; other consistent names for follow-up |
| assessment_date | ISO date, `YYYY-MM-DD` |
| lesion_id | Stable identifier across visits |
| organ | Consistent organ label |
| lesion_type | `nodal` or `non_nodal` |
| is_target | `yes` or `no`; baseline designation retained across visits |
| diameter_mm | Finite, nonnegative measurement; short axis for nodes, longest diameter for non-nodal lesions |

See [the synthetic example](examples/lesions.csv).

## Checks and interpretation

Errors flag missing or duplicate columns, empty fields, malformed rows/CSV, invalid dates, invalid enumerations, invalid measurements, and duplicate patient/visit/lesion records. Warnings flag changing lesion attributes, differing assessment dates within a visit, baseline targets below 10 mm (non-nodal) or 15 mm (nodal), more than five baseline targets per patient, and more than two per organ. Report row numbers count CSV records, including the header; quoted multiline records may span multiple physical lines.

The CLI exits 0 when checks pass, 1 when any error or warning needs review, and 2 for file/encoding failures. JSON includes counts, status, and findings; CSV contains findings only. The web API accepts a raw UTF-8 CSV body at `POST /api/check` and returns the same JSON report. `GET /health` checks server availability.

This is an initial data review aid, not a validated clinical system. Size findings are warnings because measurability also depends on modality, slice thickness, lesion characteristics, prior treatment, and the study protocol. Zero measurements at follow-up are permitted. The tool does not infer CR/PR/SD/PD, calculate best overall response, validate non-target progression or new lesions, or assess imaging adequacy. Passing QC does not establish RECIST compliance. Clinical rules need study-specific review and validation before operational use. Reference: Eisenhauer et al., European Journal of Cancer 45 (2009), 228–247, doi:10.1016/j.ejca.2008.10.026.

## Development

```sh
python -m unittest discover -s tests -v
```

Tests cover schema failures, lesion counts and sizes, longitudinal consistency, CLI reports/exit codes, and real HTTP uploads. No external services, credentials, or database are needed.
