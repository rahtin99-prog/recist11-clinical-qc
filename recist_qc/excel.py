"""One standards-based .xlsx workbook, generated without runtime dependencies."""
import csv
import io
import json
import math
import re
from datetime import datetime, timezone
from zipfile import ZIP_DEFLATED, ZipFile
from xml.etree.ElementTree import Element, SubElement, tostring

from .response import evaluate_responses
from .verification import verify_cases

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xml(element):
    return tostring(element, encoding="utf-8", xml_declaration=True)


def _column(index):
    value = ""
    while index:
        index, digit = divmod(index - 1, 26)
        value = chr(65 + digit) + value
    return value


def _sheet(rows):
    if len(rows) > 1048576 or any(len(row) > 16384 for row in rows):
        raise ValueError("Input exceeds Excel's worksheet limit of 1,048,576 rows or 16,384 columns.")
    root = Element("worksheet", xmlns=NS)
    views = SubElement(root, "sheetViews")
    view = SubElement(views, "sheetView", workbookViewId="0")
    SubElement(view, "pane", ySplit="1", topLeftCell="A2", activePane="bottomLeft", state="frozen")
    cols = SubElement(root, "cols")
    width = max((len(row) for row in rows), default=1)
    for col in range(1, width + 1):
        SubElement(cols, "col", min=str(col), max=str(col), width="28" if col < width else "65", customWidth="1")
    data = SubElement(root, "sheetData")
    for row_number, values in enumerate(rows, 1):
        row = SubElement(data, "row", r=str(row_number))
        for column, value in enumerate(values, 1):
            attrs = {"r": f"{_column(column)}{row_number}", "s": "1" if row_number == 1 else "0"}
            if value is None:
                continue
            if isinstance(value, bool):
                attrs["t"] = "b"
                cell = SubElement(row, "c", attrs)
                SubElement(cell, "v").text = "1" if value else "0"
            elif isinstance(value, (int, float)) and math.isfinite(value):
                cell = SubElement(row, "c", attrs)
                SubElement(cell, "v").text = str(value)
            else:
                # Explicit inline strings prevent Excel formula execution, including user IDs starting '='.
                attrs["t"] = "inlineStr"
                cell = SubElement(row, "c", attrs)
                text = str(value)
                text = re.sub(r"[^\x09\x0a\x0d\x20-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]", "", text)
                if len(text.encode("utf-16-le")) // 2 > 32767:
                    text = text.encode("utf-16-le")[:64000].decode("utf-16-le", errors="ignore") + " [TRUNCATED: Excel cell length limit]"
                string = SubElement(SubElement(cell, "is"), "t", {"{http://www.w3.org/XML/1998/namespace}space": "preserve"})
                string.text = text
    if rows and width:
        SubElement(root, "autoFilter", ref=f"A1:{_column(width)}{len(rows)}")
    return _xml(root)


def _table(records, columns):
    return [columns, *[[record.get(key) for key in columns] for record in records]]


def create_workbook(text, source="CSV input"):
    review = evaluate_responses(text)
    qc = review["data_qc"]
    verification = verify_cases()
    generated = datetime.now(timezone.utc).isoformat()
    reasons = []
    if qc["findings"]:
        reasons.append("Data QC findings require review")
    if review.get("blocked_reason"):
        reasons.append(review["blocked_reason"])
    if review["response_qc"]:
        reasons.append("Reported-response QC findings require review")
    if any(a["overall_response"] == "NE" for a in review["assessments"]):
        reasons.append("One or more responses are not evaluable")
    if not verification["passed"]:
        reasons.append("Built-in software checks failed")
    try:
        input_rows = list(csv.reader(io.StringIO(text.lstrip("\ufeff")), strict=True))
    except csv.Error:
        input_rows = [["Original CSV (malformed; raw physical lines)"], *[[line] for line in text.splitlines()]]
    summary = [["Item", "Value"], ["Source", source], ["Generated at (UTC)", generated],
               ["Software version", "0.3.0"], ["Review status", "REVIEW REQUIRED" if reasons else "IMPLEMENTED CHECKS PASSED"],
               ["Reasons", "; ".join(reasons) or "No findings from implemented checks"],
               ["Rows checked", qc["rows_checked"]], ["Data errors", qc["errors"]], ["Data warnings", qc["warnings"]],
               ["Response assessments", len(review["assessments"])], ["Response QC findings", len(review["response_qc"])],
               ["Not evaluable responses", sum(a["overall_response"] == "NE" for a in review["assessments"])],
               ["Reported response not supplied", sum(a["reported_response"] is None for a in review["assessments"])],
               ["Built-in expected-output checks", f"{verification['passed_count']}/{verification['total']} passed"],
               ["Test scope", verification["scope"]],
               ["Clinical scope", "Unconfirmed timepoint response review; not clinically validated; no confirmed or best overall response."],
               ["Workbook contents", "Input Data, Data QC, Responses, Response QC, Tests, Notes. Empty findings tabs have headers only."]]
    test_rows = [["Test", "Result", "Expected", "Actual"]]
    for case in verification["results"]:
        test_rows.append([case["label"], "PASS" if case["passed"] else "FAIL",
                          json.dumps(case["expected"], sort_keys=True), json.dumps(case["actual"], sort_keys=True)])
    sheets = [("Summary", summary), ("Input Data", input_rows or [["No input rows"]]),
              ("Data QC", _table(qc["findings"], ["row", "severity", "code", "message"])),
              ("Responses", _table(review["assessments"], ["patient_id", "visit", "assessment_date", "baseline_sum_mm", "prior_nadir_mm", "sum_mm", "change_from_baseline_pct", "change_from_nadir_pct", "increase_from_nadir_mm", "target_response", "overall_response", "reported_response", "comparison", "reason"])),
              ("Response QC", _table(review["response_qc"], ["patient_id", "visit", "code", "message"])),
              ("Tests", test_rows),
              ("Notes", [["Topic", "Explanation"],
                         ["Response scope", review["scope"]],
                         ["Blocked calculations", review.get("blocked_reason", "None")],
                         ["Missing assessments", "Missing new-lesion or non-target information is not assumed negative; conservative NE rules apply."],
                         ["Data QC gate", "Response review is held for the whole input file until all data QC findings are resolved."],
                         ["Nadir", "Prior minimum target sum including baseline; percentages are blank when prior nadir is zero."],
                         ["Missing reported responses", "Not supplied means a comparison was not performed, not that the response was verified."],
                         ["Tests", "Tests sheet records freshly executed synthetic expected-output checks, not the full unit/browser suite and not clinical validation."],
                         ["Excel text limits", "Cells exceeding Excel's 32,767 UTF-16-unit text limit are visibly marked as truncated. Unsupported XML control characters are removed."],
                         ["Clinical validation", "Protocol confirmation rules, best overall response, non-target-only disease and imaging adequacy are outside this version. See README.md."],
                         ["Reference", "Eisenhauer et al., European Journal of Cancer 45 (2009), 228–247. doi:10.1016/j.ejca.2008.10.026"]])]
    content = Element("Types", xmlns="http://schemas.openxmlformats.org/package/2006/content-types")
    SubElement(content, "Default", Extension="rels", ContentType="application/vnd.openxmlformats-package.relationships+xml")
    SubElement(content, "Default", Extension="xml", ContentType="application/xml")
    for part, kind in [("workbook.xml", "sheet.main"), ("styles.xml", "styles")]:
        SubElement(content, "Override", PartName="/xl/"+part, ContentType=f"application/vnd.openxmlformats-officedocument.spreadsheetml.{kind}+xml")
    workbook = Element("workbook", xmlns=NS)
    sheet_list = SubElement(workbook, "sheets")
    relationships = Element("Relationships", xmlns="http://schemas.openxmlformats.org/package/2006/relationships")
    for index, (name, _) in enumerate(sheets, 1):
        SubElement(sheet_list, "sheet", name=name, sheetId=str(index), attrib={f"{{{REL}}}id":f"rId{index}"})
        SubElement(relationships, "Relationship", Id=f"rId{index}", Type=REL+"/worksheet", Target=f"worksheets/sheet{index}.xml")
        SubElement(content, "Override", PartName=f"/xl/worksheets/sheet{index}.xml", ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml")
    SubElement(relationships, "Relationship", Id="styles", Type=REL+"/styles", Target="styles.xml")
    package_rel = Element("Relationships", xmlns="http://schemas.openxmlformats.org/package/2006/relationships")
    SubElement(package_rel, "Relationship", Id="rId1", Type=REL+"/officeDocument", Target="xl/workbook.xml")
    styles = f'''<?xml version="1.0" encoding="UTF-8"?><styleSheet xmlns="{NS}"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Calibri"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF163947"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>'''
    output = io.BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _xml(content))
        archive.writestr("_rels/.rels", _xml(package_rel))
        archive.writestr("xl/workbook.xml", _xml(workbook))
        archive.writestr("xl/_rels/workbook.xml.rels", _xml(relationships))
        archive.writestr("xl/styles.xml", styles)
        for index, (_, rows) in enumerate(sheets, 1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _sheet(rows))
    return output.getvalue()
