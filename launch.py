"""Windows-friendly launcher: verify first, then open the local app."""
import os
from pathlib import Path
import sys
import threading
import unittest
import webbrowser
from http.server import ThreadingHTTPServer


def main():
    os.chdir(Path(__file__).resolve().parent)
    if sys.version_info < (3, 11):
        print("Python 3.11 or newer is required.")
        return 1
    print("Checking the application before starting...", flush=True)
    suite = unittest.defaultTestLoader.discover("tests")
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        print("Tests failed. The app was not started; review the errors above.")
        return 1
    from recist_qc.verification import verify_cases
    from recist_qc.web import Handler
    verification = verify_cases()
    if not verification["passed"]:
        print("Expected-output verification failed. The app was not started.")
        return 1
    print(f"All tests passed. {verification['total']} sample outputs match expected results.", flush=True)
    # Select an available local port so an older app on port 8000 cannot be mistaken for this one.
    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        address = f"http://127.0.0.1:{server.server_port}"
        print(f"Opening {address}. Keep this window open. Press Ctrl+C to stop.", flush=True)
        threading.Timer(0.5, webbrowser.open, args=(address,)).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
