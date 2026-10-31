"""Local-only development server. Uploads are processed in memory."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .core import check_csv

MAX_UPLOAD = 2 * 1024 * 1024
DEMO_CSV = """patient_id,visit,assessment_date,lesion_id,organ,lesion_type,is_target,diameter_mm
SYNTHETIC-002,baseline,2026-01-01,L1,lung,non_nodal,yes,8
SYNTHETIC-002,baseline,2026-01-01,L2,lymph_nodes,nodal,yes,12
SYNTHETIC-002,week_6,2026-02-12,L1,lung,non_nodal,yes,-3
SYNTHETIC-002,week_6,2026-02-12,L1,lung,non_nodal,yes,6
"""
PAGE = """<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>RECIST 1.1 · Clinical QC</title>
<style>
body{font:16px system-ui;background:#f4f7fa;color:#193047;max-width:960px;margin:48px auto;padding:0 24px}
main{background:white;padding:32px;border-radius:16px;box-shadow:0 8px 40px #19304710}
h1{margin-top:8px}p{line-height:1.6}button,a{color:#075b76}button{padding:10px 20px;border:1px solid #075b76;border-radius:8px;background:#e5f4f7;cursor:pointer}
table{border-collapse:collapse;width:100%;margin-top:24px}td,th{padding:12px;text-align:left;border-bottom:1px solid #ddd}#summary{font-weight:600;margin:24px 0}input{margin:16px 0;max-width:100%}.muted{color:#536677} .scroll{overflow-x:auto}
</style><main><span class="muted">DATA QUALITY REVIEW</span><h1>RECIST 1.1 Clinical QC</h1>
<p>Upload a lesion measurement CSV to identify missing values, duplicates, invalid measurements, and baseline target-selection issues.</p>
<p class="muted">For data review only. This tool does not assign response categories or replace clinical assessment. Files are processed in memory and are not saved by this app. Use synthetic or de-identified data in this development server.</p>
<p>Required columns: patient_id, visit, assessment_date, lesion_id, organ, lesion_type, is_target, diameter_mm.</p>
<form id="form"><label for="file">Lesion CSV (UTF-8, maximum 2 MiB)</label><br><input id="file" type="file" accept=".csv,text/csv" required><br><button>Run quality checks</button></form>
<p><button id="demo" type="button">Try sample with QC issues</button> <a href="/sample.csv" download="lesions_with_issues.csv">Download sample CSV</a></p>
<div id="summary" role="status" aria-live="polite"></div><a id="download" hidden download="qc-report.json">Download JSON report</a>
<div class="scroll"><table hidden id="results"><thead><tr><th>Row</th><th>Severity</th><th>Check</th><th>Finding</th></tr></thead><tbody></tbody></table></div></main>
<script>
let reportUrl;
async function runCheck(file){
 const summary=document.querySelector('#summary');const table=document.querySelector('#results');const link=document.querySelector('#download');
 table.hidden=true;link.hidden=true;summary.textContent='Checking…';
 try{if(file.size>2097152)throw Error('File exceeds 2 MiB limit.');
 const response=await fetch('/api/check',{method:'POST',headers:{'Content-Type':'text/csv'},body:file});const report=await response.json();if(!response.ok)throw Error(report.error);
 summary.textContent=`${report.rows_checked} rows checked · ${report.errors} errors · ${report.warnings} warnings · ${report.status==='passed'?'Checks passed':'Review required'}`;
 const body=table.querySelector('tbody');body.replaceChildren();for(const finding of report.findings){const tr=document.createElement('tr');for(const key of ['row','severity','code','message']){const td=document.createElement('td');td.textContent=finding[key];tr.append(td);}body.append(tr);}table.hidden=!report.findings.length;
 if(reportUrl)URL.revokeObjectURL(reportUrl);reportUrl=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'}));link.href=reportUrl;link.hidden=false;
 }catch(error){summary.textContent=error.message;}
};
document.querySelector('#form').onsubmit=event=>{event.preventDefault();runCheck(document.querySelector('#file').files[0]);};
document.querySelector('#demo').onclick=()=>runCheck(new Blob([DEMO_DATA],{type:'text/csv'}));
</script></html>"""
PAGE = PAGE.replace("DEMO_DATA", json.dumps(DEMO_CSV))


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
        else:
            self.respond(404, '{"error":"Not found"}')

    def do_POST(self):
        if self.path != "/api/check":
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
        self.respond(200, json.dumps(check_csv(text)))


def serve(host="127.0.0.1", port=8000):
    with ThreadingHTTPServer((host, port), Handler) as server:
        print(f"RECIST QC development server listening on {host}:{port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
