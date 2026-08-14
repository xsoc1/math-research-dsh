"""Serve the local Blueprint Explorer with Python's standard library."""

from __future__ import annotations

import argparse
import functools
import http.server
import socketserver
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the local Blueprint Explorer.")
    parser.add_argument("--port", type=int, default=8765, help="Local TCP port (default: 8765).")
    parser.add_argument("--no-open", action="store_true", help="Do not open the default browser.")
    args = parser.parse_args()

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
    with socketserver.ThreadingTCPServer(("127.0.0.1", args.port), handler) as server:
        url = f"http://127.0.0.1:{args.port}/viewer/"
        print(f"Blueprint Explorer is available at {url}")
        print("Press Ctrl+C to stop the local server.")
        if not args.no_open:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nBlueprint Explorer stopped.")


if __name__ == "__main__":
    main()
