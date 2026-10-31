"""Local-only development server. Uploads are processed in memory."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .core import check_csv
from .ui import PAGE
from .cases import CASES
from .response_cases import RESPONSE_CSV
from .response import evaluate_responses
from .verification import verify_cases

MAX_UPLOAD = 2 * 1024 * 1024
DEMO_CSV = """patient_id,visit,assessment_date,lesion_id,organ,lesion_type,is_target,diameter_mm
SYNTHETIC-002,baseline,2026-01-01,L1,lung,non_nodal,yes,8
SYNTHETIC-002,baseline,2026-01-01,L2,lymph_nodes,nodal,yes,12
SYNTHETIC-002,week_6,2026-02-12,L1,lung,non_nodal,yes,-3
SYNTHETIC-002,week_6,2026-02-12,L1,lung,non_nodal,yes,6
"""


def examples():
    return [{"id": "responses", "label": "RECIST responses and reported-response checks",
             "description": "Expected: 8 follow-ups, 2 response mismatches, and 1 response that cannot be verified because assessment flags are missing."},
            *[{"id": c["id"], "label": c["label"],
               "description": f"Expected data QC: {c['expected']['rows_checked']} rows, {c['expected']['errors']} errors, {c['expected']['warnings']} warnings."}
              for c in CASES]]



class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Avoid recording uploaded data or request paths.

    def respond(self, status, body, content_type="application/json"):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/":
            self.respond(200, PAGE, "text/html")
        elif self.path == "/health":
            self.respond(200, '{"status":"ok"}')
        elif self.path == "/sample.csv":
            self.respond(200, DEMO_CSV, "text/csv")
        elif self.path == "/api/examples":
            self.respond(200, json.dumps(examples()))
        elif self.path == "/api/self-test":
            self.respond(200, json.dumps(verify_cases()))
        elif self.path.startswith("/api/examples/") and self.path.endswith(".csv"):
            name = self.path.removeprefix("/api/examples/").removesuffix(".csv")
            sample = RESPONSE_CSV if name == "responses" else next((c["csv"] for c in CASES if c["id"] == name), None)
            if sample is None:
                self.respond(404, '{"error":"Unknown example"}')
            else:
                self.respond(200, sample, "text/csv")
        else:
            self.respond(404, '{"error":"Not found"}')

    def do_POST(self):
        if self.path not in {"/api/check", "/api/analyze", "/api/responses"}:
            self.respond(404, '{"error":"Not found"}')
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            size = 0
        if size <= 0 or size > MAX_UPLOAD:
            self.respond(413, '{"error":"Supply a CSV body between 1 byte and 2 MiB."}')
            return
        self.connection.settimeout(10)
        try:
            text = self.rfile.read(size).decode("utf-8-sig")
        except (UnicodeError, OSError):
            self.respond(400, '{"error":"Unable to read a UTF-8 CSV file."}')
            return
        if self.path == "/api/check":
            report = check_csv(text)
        elif self.path == "/api/responses":
            report = evaluate_responses(text)
        else:
            response_review = evaluate_responses(text)
            report = {"data_qc": response_review["data_qc"], "response_review": response_review,
                      "report_version": "0.2.0"}
        self.respond(200, json.dumps(report))


def serve(host="127.0.0.1", port=8000):
    with ThreadingHTTPServer((host, port), Handler) as server:
        print(f"RECIST QC development server listening on {host}:{port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
