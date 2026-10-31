import argparse
import json
import sys
from pathlib import Path

from .core import check_csv, findings_csv


def main():
    parser = argparse.ArgumentParser(description="Review lesion CSV data quality.")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="Generate a QC report")
    check.add_argument("input", type=Path)
    check.add_argument("--format", choices=("json", "csv"), default="json")
    check.add_argument("--output", type=Path)
    serve = sub.add_parser("serve", help="Start the local CSV review web app")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.command == "serve":
        from .web import serve as run_server
        run_server(args.host, args.port)
        return 0
    try:
        report = check_csv(args.input.read_text(encoding="utf-8-sig"))
        output = json.dumps(report, indent=2) + "\n" if args.format == "json" else findings_csv(report)
        if args.output:
            args.output.write_text(output, encoding="utf-8")
        else:
            sys.stdout.write(output)
        return 1 if report["findings"] else 0
    except (OSError, UnicodeError) as exc:
        print(f"Unable to process file: {exc}", file=sys.stderr)
        return 2
