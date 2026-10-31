"""Conservative, row-level QC; does not assign clinical response categories."""

import csv
import io
import math
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date

FIELDS = ("patient_id", "visit", "assessment_date", "lesion_id", "organ",
          "lesion_type", "is_target", "diameter_mm")


@dataclass(frozen=True)
class Finding:
    row: int
    severity: str
    code: str
    message: str


def check_csv(text: str) -> dict:
    findings = []

    def add(row, severity, code, message):
        findings.append(Finding(row, severity, code, message))

    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")), strict=True)
    try:
        headers = reader.fieldnames or []
        missing = sorted(set(FIELDS) - set(headers))
        if missing:
            add(1, "error", "MISSING_COLUMNS", "Missing columns: " + ", ".join(missing))
        if len(headers) != len(set(headers)):
            add(1, "error", "DUPLICATE_COLUMNS", "Column names must be unique.")
        if findings:
            return _report(0, findings)
        seen = set()
        baseline_targets = defaultdict(list)
        identities = {}
        visit_dates = {}
        row_count = 0
        for line, raw in enumerate(reader, 2):
            row_count += 1
            if None in raw or any(raw.get(k) is None for k in FIELDS):
                add(line, "error", "ROW_SHAPE", "Row does not match the CSV header.")
                continue
            row = {k: (raw[k] or "").strip() for k in FIELDS}
            empty = [k for k, v in row.items() if not v]
            if empty:
                add(line, "error", "REQUIRED_VALUE", "Empty fields: " + ", ".join(empty))
                continue
            patient, visit, lesion = row["patient_id"], row["visit"].lower(), row["lesion_id"]
            key = patient, visit, lesion
            if key in seen:
                add(line, "error", "DUPLICATE_LESION", "Lesion appears more than once in this patient visit.")
            seen.add(key)
            try:
                date.fromisoformat(row["assessment_date"])
                if len(row["assessment_date"]) != 10:
                    raise ValueError()
            except ValueError:
                add(line, "error", "INVALID_DATE", "Use a valid YYYY-MM-DD assessment date.")
            date_key = patient, visit
            if date_key in visit_dates and visit_dates[date_key] != row["assessment_date"]:
                add(line, "warning", "VISIT_DATE_MISMATCH", "Assessment dates differ within a patient visit; review acquisition timing.")
            visit_dates[date_key] = row["assessment_date"]
            kind = row["lesion_type"].lower()
            target = row["is_target"].lower()
            organ = row["organ"].lower()
            if kind not in {"nodal", "non_nodal"}:
                add(line, "error", "INVALID_LESION_TYPE", "lesion_type must be nodal or non_nodal.")
            if target not in {"yes", "no"}:
                add(line, "error", "INVALID_TARGET", "is_target must be yes or no.")
            identity = patient, lesion
            attributes = organ, kind, target
            if identity in identities and identities[identity] != attributes:
                add(line, "warning", "LESION_CHANGED", "Organ, lesion type, or target designation changes across visits.")
            identities[identity] = attributes
            try:
                diameter = float(row["diameter_mm"])
                if not math.isfinite(diameter) or diameter < 0:
                    raise ValueError()
            except ValueError:
                add(line, "error", "INVALID_DIAMETER", "diameter_mm must be a finite nonnegative number.")
                diameter = None
            if visit == "baseline" and target == "yes":
                baseline_targets[patient].append((line, organ, lesion))
                threshold = 15 if kind == "nodal" else 10
                if diameter is not None and kind in {"nodal", "non_nodal"} and diameter < threshold:
                    add(line, "warning", "BASELINE_TARGET_SIZE", f"Baseline target is below {threshold} mm; review measurability and imaging criteria.")
        for patient, targets in baseline_targets.items():
            unique = {(organ, lesion) for _, organ, lesion in targets}
            if len(unique) > 5:
                add(targets[0][0], "warning", "TARGET_COUNT", "Patient has more than five baseline target lesions.")
            for organ in {o for o, _ in unique}:
                if sum(o == organ for o, _ in unique) > 2:
                    add(next(n for n, o, _ in targets if o == organ), "warning", "ORGAN_TARGET_COUNT", "More than two baseline targets in one organ.")
        if not row_count:
            add(1, "error", "NO_DATA", "CSV contains no data rows.")
        return _report(row_count, findings)
    except csv.Error as exc:
        add(reader.line_num, "error", "INVALID_CSV", f"Malformed CSV: {exc}")
        return _report(0, findings)


def _report(rows, findings):
    errors = sum(f.severity == "error" for f in findings)
    warnings = sum(f.severity == "warning" for f in findings)
    return {"rows_checked": rows, "errors": errors, "warnings": warnings,
            "status": "review_required" if findings else "passed",
            "findings": [asdict(f) for f in findings]}


def findings_csv(report):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=("row", "severity", "code", "message"))
    writer.writeheader()
    writer.writerows(report["findings"])
    return output.getvalue()
