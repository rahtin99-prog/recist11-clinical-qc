"""Unconfirmed timepoint response review for baseline-selected target lesions.

Uses explicit new-lesion and non-target assessments; never infers their absence.
Does not calculate confirmed response, best overall response, or iRECIST.
"""
import csv
import io
from collections import defaultdict
from decimal import Decimal

from .core import check_csv

RESPONSE_COLUMNS = ("new_lesions", "non_target_response", "reported_response")
NON_TARGET = {"CR", "NON_CR_NON_PD", "PD", "NE", "NOT_APPLICABLE"}
CATEGORIES = {"CR", "PR", "SD", "PD", "NE"}


def evaluate_responses(text):
    qc = check_csv(text)
    result = {"data_qc": qc, "assessments": [], "response_qc": [],
              "scope": "Unconfirmed timepoint response review. No best overall response or protocol confirmation rules."}
    if qc["findings"]:
        result["blocked_reason"] = "Resolve data QC errors and warnings before calculating responses."
        return result
    rows = list(csv.DictReader(io.StringIO(text.lstrip("\ufeff"))))
    patients = defaultdict(lambda: defaultdict(list))
    for raw in rows:
        row = {key: (value or "").strip() for key, value in raw.items() if key is not None}
        patients[row["patient_id"]][row["visit"].lower()].append(row)
    for patient, visits in patients.items():
        baseline = visits.get("baseline", [])
        targets = {r["lesion_id"]: r for r in baseline if r["is_target"].lower() == "yes"}
        baseline_dates = {r["assessment_date"] for r in baseline}
        baseline_sum = sum((Decimal(r["diameter_mm"]) for r in targets.values()), Decimal(0))
        nadir = baseline_sum
        blocked = None
        if not baseline or not targets or baseline_sum <= 0:
            blocked = "A measurable baseline target-lesion set is required. Non-target-only disease is outside this workflow."
        elif len(baseline_dates) != 1:
            blocked = "Baseline must have one assessment date."
        followups = sorted(((name, data) for name, data in visits.items() if name != "baseline"),
                           key=lambda item: item[1][0]["assessment_date"])
        dates = [data[0]["assessment_date"] for _, data in followups]
        if len(dates) != len(set(dates)):
            blocked = "Different follow-up visits share an assessment date; chronological order is ambiguous."
        for visit, data in followups:
            reason = blocked
            current = {r["lesion_id"]: r for r in data if r["is_target"].lower() == "yes"}
            assessment = {"patient_id": patient, "visit": visit, "assessment_date": data[0]["assessment_date"],
                          "baseline_sum_mm": float(baseline_sum), "prior_nadir_mm": float(nadir),
                          "sum_mm": None, "change_from_baseline_pct": None,
                          "change_from_nadir_pct": None, "increase_from_nadir_mm": None,
                          "target_response": "NE", "overall_response": "NE"}
            if baseline_dates and data[0]["assessment_date"] <= min(baseline_dates):
                reason = "Follow-up must occur after baseline."
            if set(current) != set(targets):
                reason = "Follow-up must contain exactly the baseline target-lesion IDs; missing lesions are not assumed to be zero."
            if reason:
                assessment["reason"] = reason
                # Unknown target history cannot establish a later nadir.
                blocked = "Earlier target assessment was incomplete or ambiguous; nadir cannot be established."
            else:
                total = sum((Decimal(r["diameter_mm"]) for r in current.values()), Decimal(0))
                delta = total - nadir
                pct_baseline = (total - baseline_sum) / baseline_sum * 100
                pct_nadir = delta / nadir * 100 if nadir else None
                complete = all(Decimal(r["diameter_mm"]) < 10 if r["lesion_type"].lower() == "nodal"
                               else Decimal(r["diameter_mm"]) == 0 for r in current.values())
                if complete:
                    target, target_reason = "CR", "All non-nodal targets are zero and every target node is below 10 mm short axis."
                elif total >= nadir * Decimal("1.2") and delta >= 5:
                    target, target_reason = "PD", "Target sum increased at least 20% and at least 5 mm from the prior nadir."
                elif total <= baseline_sum * Decimal("0.7"):
                    target, target_reason = "PR", "Target sum decreased at least 30% from baseline without target progression."
                else:
                    target, target_reason = "SD", "Target measurements meet neither CR, PR nor PD thresholds."
                assessment.update(sum_mm=float(total), change_from_baseline_pct=round(float(pct_baseline), 4),
                                  change_from_nadir_pct=round(float(pct_nadir), 4) if pct_nadir is not None else None,
                                  increase_from_nadir_mm=float(delta), target_response=target)
                new = {r.get("new_lesions", "").lower() for r in data}
                non_target = {r.get("non_target_response", "").upper() for r in data}
                if len(new) != 1 or len(non_target) != 1:
                    overall, overall_reason = "NE", "Assessment flags must agree across every row in this visit."
                else:
                    new_value, nt = next(iter(new)), next(iter(non_target))
                    overall, overall_reason = combine_response(target, nt, new_value)
                assessment.update(overall_response=overall, reason=target_reason + " " + overall_reason)
                nadir = min(nadir, total)
            reported = {r.get("reported_response", "").upper() for r in data}
            submitted = next(iter(reported)) if len(reported) == 1 else "INCONSISTENT"
            assessment["reported_response"] = submitted or None
            if submitted and submitted not in CATEGORIES:
                result["response_qc"].append({"patient_id": patient, "visit": visit, "code": "INVALID_REPORTED_RESPONSE",
                                              "message": "Reported response must be consistent across rows and one of CR, PR, SD, PD, NE."})
                assessment["comparison"] = "invalid reported response"
            elif submitted and submitted != assessment["overall_response"]:
                code = "RESPONSE_NOT_EVALUABLE" if assessment["overall_response"] == "NE" else "RESPONSE_MISMATCH"
                result["response_qc"].append({"patient_id": patient, "visit": visit, "code": code,
                                              "message": f"Reported {submitted}; calculated {assessment['overall_response']}. " + assessment["reason"]})
                assessment["comparison"] = "cannot verify" if code == "RESPONSE_NOT_EVALUABLE" else "mismatch"
            elif submitted:
                assessment["comparison"] = "matches" if submitted != "NE" else "both not evaluable"
            else:
                assessment["comparison"] = "not supplied"
            result["assessments"].append(assessment)
    if not result["assessments"]:
        result["blocked_reason"] = "No follow-up visits found. Include a baseline and at least one later visit."
    return result


def combine_response(target, non_target, new_lesions):
    if new_lesions not in {"yes", "no", "unknown"} or non_target not in NON_TARGET:
        return "NE", "Supply new_lesions=yes/no/unknown and non_target_response=CR/NON_CR_NON_PD/PD/NE/NOT_APPLICABLE."
    if new_lesions == "yes" or non_target == "PD" or target == "PD":
        return "PD", "Progression is indicated by targets, unequivocal non-target progression, or unequivocal new lesions."
    if new_lesions == "unknown" or non_target == "NE" or target == "NE":
        return "NE", "A required disease assessment is not evaluable."
    if target == "CR":
        if non_target in {"CR", "NOT_APPLICABLE"}:
            return "CR", "Target and non-target assessments support complete response with no new lesions."
        return "PR", "Targets resolved but non-target disease persists, with no new lesions."
    return target, "No new lesions or non-target progression change the target response."
