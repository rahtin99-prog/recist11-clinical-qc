# Software verification — version 0.3.0

Executed in the cloud workspace on 2026-10-31, using Python 3.12 and Chromium on Linux.

| Check | Result |
| --- | --- |
| `python -m unittest discover -s tests -v` | 36 tests passed; none skipped |
| Built-in fixed expected-output checks | 15 of 15 passed |
| Real Chromium: all seven selectable examples | Passed |
| Browser: CSV uploads and invalid-schema handling | Passed |
| Browser: complete JSON, response CSV, response-findings CSV and test-evidence downloads | Passed; contents checked |
| Browser: narrow-screen layout | Passed at 390 px; no page overflow |
| Browser: JavaScript errors | None observed during tested workflows |
| Launcher backend: tests, expected outputs, available-port startup and HTTP readiness | Passed; browser opening replaced with a stub for this automated check |
| Previous editable package installation | Version 0.2.0 installed successfully; runtime Excel export uses only the standard library |

Response tests include the exact 30% PR threshold; both PD requirements; PD against prior nadir even after a baseline-relative PR; normal-node CR threshold; zero non-nodal target size; zero nadir; new lesions; non-target progression; missing/inconsistent flags; invalid/reported response mismatches; missing target IDs/baseline; out-of-order or invalid dates; and the CLI/HTTP workflow. The response-combination test covers 75 combinations.

The response demonstration contains eight follow-up assessments and intentionally produces two reported-response mismatches plus one unverifiable response due to missing disease flags. The data QC for that demonstration passes. Those response findings are expected test outcomes, not failed software tests.

The Windows batch wrapper has not been executed on Windows in this cloud test run. Its Python launcher backend was exercised on Linux; native Windows startup and automatic browser opening remain platform checks for the downloaded copy. Print/PDF uses the browser's native print dialog and has not been independently PDF-render-tested here.

These results establish the behavior of the implemented software on synthetic fixtures. They do not establish clinical validation, complete RECIST implementation, confirmed response or best overall response. See README.md for the exact input requirements, conservative NE behavior and scope limits. The in-app self-test output is available from `/api/self-test`; a saved example is in `examples/builtin_test_evidence.json`.

## Single Excel workbook verification

Version 0.3.0 adds an actual OOXML `.xlsx` workbook and replaces the web app’s separate report downloads with one Excel download. 36 unit/CLI/HTTP tests passed. Real Chromium downloads were independently read with openpyxl 3.1.5: all seven tabs, eight response assessments, three response QC findings, and 15 passing expected-output checks were verified. Negative percentage changes retain Excel numeric types. A second upload with data QC findings verified those findings are exported and blocked responses leave a header-only Responses tab. Formula-shaped text is stored as explicit text, and XML-special/control characters are handled. No Microsoft Excel application was available in the cloud test environment; native Excel UI opening was not directly tested. A generated demonstration workbook is included at `examples/complete-qc-report.xlsx`.
