import csv
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest

from recist_qc.core import FIELDS
from recist_qc.response import combine_response, evaluate_responses
from recist_qc.verification import verify_cases


def dataset(measurements, *, nodal=False, new="no", non_target="NOT_APPLICABLE", reported=""):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow((*FIELDS, "new_lesions", "non_target_response", "reported_response"))
    for i, size in enumerate(measurements):
        writer.writerow(["P1", "baseline" if i == 0 else f"visit_{i}", f"2026-{i+1:02d}-01", "L1",
                         "lymph_nodes" if nodal else "lung", "nodal" if nodal else "non_nodal", "yes", size,
                         new, non_target, reported])
    return output.getvalue()


class ResponseTests(unittest.TestCase):
    def response(self, values, **kwargs):
        return evaluate_responses(dataset(values, **kwargs))["assessments"][-1]

    def test_partial_response_exact_threshold(self):
        self.assertEqual(self.response([100, 70])["overall_response"], "PR")
        self.assertEqual(self.response([100, 70.01])["overall_response"], "SD")

    def test_pd_requires_both_thresholds(self):
        self.assertEqual(self.response([10, 12])["overall_response"], "SD")
        self.assertEqual(self.response([10, 15])["overall_response"], "PD")
        self.assertEqual(self.response([100, 119.99])["overall_response"], "SD")
        self.assertEqual(self.response([100, 120])["overall_response"], "PD")

    def test_uses_prior_nadir_and_pd_overrides_pr(self):
        assessment = self.response([100, 50, 60])
        self.assertEqual(assessment["overall_response"], "PD")
        self.assertEqual(assessment["prior_nadir_mm"], 50)
        self.assertEqual(assessment["change_from_baseline_pct"], -40)

    def test_node_cr_threshold(self):
        self.assertEqual(self.response([20, 9.99], nodal=True)["overall_response"], "CR")
        self.assertEqual(self.response([20, 10], nodal=True)["overall_response"], "PR")

    def test_non_nodal_cr_requires_zero(self):
        self.assertEqual(self.response([100, 0])["overall_response"], "CR")
        self.assertEqual(self.response([100, 0.1])["overall_response"], "PR")

    def test_zero_nadir(self):
        self.assertEqual(self.response([100, 0, 5])["overall_response"], "PD")
        self.assertIsNone(self.response([100, 0, 5])["change_from_nadir_pct"])
        self.assertEqual(self.response([100, 0, 4])["overall_response"], "PR")

    def test_new_and_non_target_progression(self):
        self.assertEqual(self.response([100, 70], new="yes")["overall_response"], "PD")
        self.assertEqual(self.response([100, 70], non_target="PD")["overall_response"], "PD")
        self.assertEqual(self.response([100, 0], non_target="NON_CR_NON_PD")["overall_response"], "PR")

    def test_missing_or_unknown_flags_not_assumed_negative(self):
        for flag in ("", "unknown", "invalid"):
            self.assertEqual(self.response([100, 70], new=flag)["overall_response"], "NE")
        self.assertEqual(self.response([100, 70], non_target="")["overall_response"], "NE")

    def test_positive_progression_with_unknown_other_assessment(self):
        self.assertEqual(combine_response("SD", "PD", "unknown")[0], "PD")

    def test_reported_response_comparison(self):
        report = evaluate_responses(dataset([100, 70], reported="SD"))
        self.assertEqual(report["response_qc"][0]["code"], "RESPONSE_MISMATCH")
        self.assertEqual(self.response([100, 70], reported="PR")["comparison"], "matches")
        report = evaluate_responses(dataset([100, 70], reported="bogus"))
        self.assertEqual(report["response_qc"][0]["code"], "INVALID_REPORTED_RESPONSE")

    def test_quality_findings_block_responses(self):
        report = evaluate_responses(dataset([8, 6]))
        self.assertIn("blocked_reason", report)
        self.assertEqual(report["assessments"], [])

    def test_missing_baseline_and_missing_lesions(self):
        text = dataset([100, 70]).replace("baseline", "initial")
        self.assertTrue(all(a["overall_response"] == "NE" for a in evaluate_responses(text)["assessments"]))
        text = dataset([100, 70]).replace("visit_1,2026-02-01,L1", "visit_1,2026-02-01,L2")
        self.assertEqual(evaluate_responses(text)["assessments"][0]["overall_response"], "NE")

    def test_dates_and_sort_order(self):
        text = dataset([100, 50, 60])
        lines = text.splitlines()
        reordered = "\n".join([lines[0], lines[3], lines[1], lines[2]]) + "\n"
        self.assertEqual(evaluate_responses(reordered)["assessments"][-1]["overall_response"], "PD")
        text = text.replace("2026-02-01", "2025-02-01")
        self.assertEqual(evaluate_responses(text)["assessments"][0]["overall_response"], "NE")

    def test_baseline_only(self):
        self.assertIn("blocked_reason", evaluate_responses(dataset([100])))

    def test_builtin_expected_outputs(self):
        report = verify_cases()
        self.assertTrue(report["passed"], report)
        self.assertEqual(report["total"], 15)

    def test_response_cli(self):
        run = subprocess.run([sys.executable, "-m", "recist_qc", "responses", "examples/response_review.csv"], capture_output=True, text=True)
        self.assertEqual(run.returncode, 1, run.stderr)
        self.assertEqual(len(json.loads(run.stdout)["assessments"]), 8)

    def test_conflicting_assessment_flags(self):
        text = Path("examples/response_review.csv").read_text()
        text = text.replace("L2,lymph_nodes,nodal,yes,8,no,CR,CR", "L2,lymph_nodes,nodal,yes,8,yes,CR,CR")
        report = evaluate_responses(text)
        assessment = next(a for a in report["assessments"] if a["patient_id"] == "SYNTHETIC-CR")
        self.assertEqual(assessment["overall_response"], "NE")

    def test_all_combinations_produce_known_category(self):
        for target in ("CR", "PR", "SD", "PD", "NE"):
            for nt in ("CR", "NON_CR_NON_PD", "PD", "NE", "NOT_APPLICABLE"):
                for new in ("yes", "no", "unknown"):
                    with self.subTest(target=target, nt=nt, new=new):
                        actual = combine_response(target, nt, new)[0]
                        self.assertIn(actual, {"CR", "PR", "SD", "PD", "NE"})
                        if new == "yes" or nt == "PD" or target == "PD":
                            self.assertEqual(actual, "PD")


if __name__ == "__main__":
    unittest.main()
