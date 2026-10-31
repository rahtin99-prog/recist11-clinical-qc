"""Compare actual QC output with fixed expected findings on synthetic cases."""
from collections import Counter

from .cases import CASES
from .core import check_csv
from .response import evaluate_responses
from .response_cases import RESPONSE_CSV, EXPECTED


def verify_cases():
    results = []
    for case in CASES:
        report = check_csv(case["csv"])
        actual = {key: report[key] for key in ("rows_checked", "errors", "warnings")}
        actual["codes"] = dict(Counter(f["code"] for f in report["findings"]))
        results.append({"id": case["id"], "label": case["label"],
                        "passed": actual == case["expected"],
                        "expected": case["expected"], "actual": actual})
    response_review = evaluate_responses(RESPONSE_CSV)
    for patient, category in EXPECTED.items():
        matches = [r for r in response_review["assessments"] if r["patient_id"] == patient]
        actual = matches[0]["overall_response"] if len(matches) == 1 else None
        results.append({"id": patient, "label": "Response: " + patient.removeprefix("SYNTHETIC-"),
                        "passed": actual == category, "expected": category, "actual": actual})
    response_codes = dict(Counter(f["code"] for f in response_review["response_qc"]))
    expected_codes = {"RESPONSE_MISMATCH": 2, "RESPONSE_NOT_EVALUABLE": 1}
    results.append({"id": "response-comparisons", "label": "Reported response comparisons",
                    "passed": response_codes == expected_codes, "expected": expected_codes, "actual": response_codes})
    return {"passed": all(r["passed"] for r in results), "total": len(results),
            "passed_count": sum(r["passed"] for r in results), "results": results,
            "scope": "Synthetic regression checks of implemented data and response rules; not clinical validation."}
