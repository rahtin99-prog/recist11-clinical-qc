import json
import subprocess
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, build_opener, ProxyHandler

from recist_qc.core import FIELDS, check_csv
from recist_qc.web import Handler

HEADER = ",".join(FIELDS) + "\n"
VALID = "P1,baseline,2026-01-01,L1,lung,non_nodal,yes,20\n"


class QualityTests(unittest.TestCase):
    def codes(self, text):
        return {f["code"] for f in check_csv(text)["findings"]}

    def test_valid_sample(self):
        report = check_csv(Path("examples/lesions.csv").read_text())
        self.assertEqual((report["rows_checked"], report["status"]), (4, "passed"))

    def test_schema_and_empty(self):
        self.assertIn("MISSING_COLUMNS", self.codes("foo\nbar\n"))
        self.assertIn("NO_DATA", self.codes(HEADER))
        self.assertIn("DUPLICATE_COLUMNS", self.codes(HEADER.rstrip() + ",visit\n"))

    def test_invalid_values(self):
        bad = "P1,baseline,2026-02-30,L1,lung,other,maybe,nan\n"
        self.assertEqual(self.codes(HEADER + bad), {"INVALID_DATE", "INVALID_LESION_TYPE", "INVALID_TARGET", "INVALID_DIAMETER"})
        self.assertIn("INVALID_DIAMETER", self.codes(HEADER + VALID.replace(",20\n", ",-1\n")))
        self.assertIn("INVALID_DATE", self.codes(HEADER + VALID.replace("2026-01-01", "2026-W01-1")))

    def test_duplicate_and_malformed(self):
        self.assertIn("DUPLICATE_LESION", self.codes(HEADER + VALID * 2))
        self.assertIn("ROW_SHAPE", self.codes(HEADER + "P1,baseline\n"))
        self.assertIn("INVALID_CSV", self.codes(HEADER + '"unterminated'))

    def test_size_and_target_limits(self):
        rows = "".join(f"P1,baseline,2026-01-01,L{i},lung,nodal,yes,14\n" for i in range(6))
        self.assertEqual(self.codes(HEADER + rows), {"BASELINE_TARGET_SIZE", "TARGET_COUNT", "ORGAN_TARGET_COUNT"})

    def test_followup_shrinkage_is_allowed(self):
        self.assertEqual(self.codes(HEADER + VALID + VALID.replace("baseline", "week6").replace(",20\n", ",0\n")), set())

    def test_longitudinal_change(self):
        text = HEADER + VALID + VALID.replace("baseline", "week6").replace("lung", "liver")
        self.assertIn("LESION_CHANGED", self.codes(text))

    def test_cli_exit_and_formats(self):
        run = subprocess.run([sys.executable, "-m", "recist_qc", "check", "examples/lesions.csv"], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)["rows_checked"], 4)
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.csv"
            path.write_text(HEADER + VALID * 2)
            run = subprocess.run([sys.executable, "-m", "recist_qc", "check", str(path), "--format", "csv"], capture_output=True, text=True)
            self.assertEqual(run.returncode, 1)
            self.assertIn("DUPLICATE_LESION", run.stdout)


class WebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"
        cls.client = build_opener(ProxyHandler({}))

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_page_and_upload(self):
        with self.client.open(self.url) as response:
            self.assertIn(b"Run quality checks", response.read())
        request = Request(self.url + "/api/check", data=(HEADER + VALID * 2).encode(), headers={"Content-Type": "text/csv"})
        with self.client.open(request) as response:
            report = json.load(response)
            self.assertEqual(report["errors"], 1)
            self.assertEqual(report["findings"][0]["code"], "DUPLICATE_LESION")

    def test_reject_invalid_encoding_and_empty_upload(self):
        for data, status in [(b"\xff", 400), (b"", 413)]:
            with self.assertRaises(HTTPError) as error:
                self.client.open(Request(self.url + "/api/check", data=data))
            self.assertEqual(error.exception.code, status)

    def test_demo_sample(self):
        with self.client.open(self.url + "/sample.csv") as response:
            sample = response.read()
        self.assertEqual(sample, Path("examples/lesions_with_issues.csv").read_bytes())
        with self.client.open(Request(self.url + "/api/check", data=sample)) as response:
            report = json.load(response)
        self.assertEqual((report["rows_checked"], report["errors"], report["warnings"]), (4, 2, 2))

    def test_complete_workflow_and_expected_tests(self):
        with self.client.open(self.url + "/api/examples") as response:
            examples = json.load(response)
        self.assertEqual(len(examples), 7)
        with self.client.open(self.url + "/api/examples/responses.csv") as response:
            sample = response.read()
        with self.client.open(Request(self.url + "/api/analyze", data=sample)) as response:
            report = json.load(response)
        self.assertEqual(report["data_qc"]["errors"], 0)
        self.assertEqual(len(report["response_review"]["assessments"]), 8)
        self.assertEqual(len(report["response_review"]["response_qc"]), 3)
        with self.client.open(self.url + "/api/self-test") as response:
            report = json.load(response)
        self.assertTrue(report["passed"])
        self.assertEqual(report["passed_count"], 15)

    def test_unknown_example_and_oversized_upload(self):
        with self.assertRaises(HTTPError) as error:
            self.client.open(self.url + "/api/examples/not-real.csv")
        self.assertEqual(error.exception.code, 404)
        request = Request(self.url + "/api/analyze", data=b"x", headers={"Content-Length": str(2*1024*1024+1)})
        with self.assertRaises(HTTPError) as error:
            self.client.open(request)
        self.assertEqual(error.exception.code, 413)


if __name__ == "__main__":
    unittest.main()
