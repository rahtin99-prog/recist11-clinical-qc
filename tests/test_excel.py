import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from recist_qc.excel import NS, create_workbook


def read_rows(archive, index):
    root = ET.fromstring(archive.read(f"xl/worksheets/sheet{index}.xml"))
    rows = []
    for row in root.findall(f"{{{NS}}}sheetData/{{{NS}}}row"):
        values = {}
        for cell in row:
            if cell.get("t") == "inlineStr":
                value = cell.find(f"{{{NS}}}is/{{{NS}}}t").text or ""
            else:
                value = cell.find(f"{{{NS}}}v").text
            values[cell.get("r")] = value
        rows.append(values)
    return rows


class ExcelTests(unittest.TestCase):
    def test_complete_workbook_and_numeric_calculations(self):
        sample = Path("examples/response_review.csv").read_text()
        with ZipFile(io.BytesIO(create_workbook(sample, "my-input.csv"))) as archive:
            self.assertIsNone(archive.testzip())
            for name in archive.namelist():
                ET.fromstring(archive.read(name))
            workbook = ET.fromstring(archive.read("xl/workbook.xml"))
            self.assertEqual([s.get("name") for s in workbook.find(f"{{{NS}}}sheets")],
                             ["Summary", "Input Data", "Data QC", "Responses", "Response QC", "Tests", "Notes"])
            summary = read_rows(archive, 1)
            self.assertEqual(summary[1]["B2"], "my-input.csv")
            self.assertEqual(len(read_rows(archive, 2)), 33)
            self.assertEqual(len(read_rows(archive, 3)), 1)
            responses = read_rows(archive, 4)
            self.assertEqual(len(responses), 9)
            self.assertEqual(responses[1]["K2"], "CR")
            self.assertEqual(responses[1]["G2"], "-92.0")
            self.assertEqual(len(read_rows(archive, 5)), 4)
            tests = read_rows(archive, 6)
            self.assertEqual(len(tests), 16)
            self.assertTrue(all(row[f"B{i}"] == "PASS" for i, row in enumerate(tests[1:], 2)))

    def test_blocked_response_and_empty_input(self):
        for sample in ("", "wrong\nvalue\n", '"unterminated'):
            with self.subTest(sample=sample), ZipFile(io.BytesIO(create_workbook(sample))) as archive:
                self.assertGreater(len(read_rows(archive, 3)), 1)
                self.assertEqual(len(read_rows(archive, 4)), 1)
                summary = " ".join(v for row in read_rows(archive, 1) for v in row.values())
                self.assertIn("REVIEW REQUIRED", summary)

    def test_text_is_not_a_formula_and_xml_is_safe(self):
        sample = Path("examples/response_review.csv").read_text().replace("SYNTHETIC-CR", '=HYPERLINK("bad")&<x>')
        # Use a valid quoted CSV cell for the formula-shaped identifier.
        sample = sample.replace('=HYPERLINK("bad")&<x>', '"=HYPERLINK(""bad"")&<x>"')
        with ZipFile(io.BytesIO(create_workbook(sample, "name\x00<&>.csv"))) as archive:
            for name in archive.namelist():
                root = ET.fromstring(archive.read(name))
                self.assertEqual(root.findall(f".//{{{NS}}}f"), [])
            self.assertEqual(read_rows(archive, 1)[1]["B2"], "name<&>.csv")
            self.assertEqual(read_rows(archive, 2)[1]["A2"], '=HYPERLINK("bad")&<x>')

    def test_cli_writes_workbook_with_findings_exit_status(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "complete.xlsx"
            result = subprocess.run([sys.executable, "-m", "recist_qc", "excel", "examples/response_review.csv", "--output", str(output)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, result.stderr)
            with ZipFile(output) as archive:
                self.assertEqual(len(read_rows(archive, 4)), 9)
