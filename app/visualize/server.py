"""
Visualize server — spins up a local Flask server, opens the dashboard in
the browser, and shuts down cleanly when the user clicks Exit or closes tab.

Called from cli.py via start_visualize(). Blocks until the server exits,
then control returns to the CLI prompt.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

PORT = 5051
_server: HTTPServer | None = None


def _load_trades(db_path: str) -> tuple[list[dict], dict]:
    """Read all trades and stats from SQLite."""
    if not Path(db_path).exists():
        return [], {}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    trades = [dict(row) for row in conn.execute(
        "SELECT * FROM trades ORDER BY scan_date DESC"
    ).fetchall()]

    stats_row = conn.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status='pending'       THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN status='resolved_win'  THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN status='resolved_loss' THEN 1 ELSE 0 END) as losses,
            AVG(CASE WHEN status IN ('resolved_win','resolved_loss') THEN pnl_estimate END) as avg_pnl,
            AVG(CASE WHEN status='resolved_win'  THEN pnl_estimate END) as avg_win,
            AVG(CASE WHEN status='resolved_loss' THEN pnl_estimate END) as avg_loss
        FROM trades
    """).fetchone()
    stats = dict(stats_row) if stats_row else {}
    conn.close()
    return trades, stats


class _Handler(BaseHTTPRequestHandler):
    db_path: str = ""
    dashboard_html: str = ""

    def log_message(self, *args):
        pass  # suppress request logs

    def do_GET(self):
        if self.path == "/":
            body = self.dashboard_html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        elif self.path == "/data":
            trades, stats = _load_trades(self.db_path)
            body = json.dumps({"trades": trades, "stats": stats}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/exit":
            self.send_response(200)
            self.end_headers()
            # Shut down server in a thread so this request can complete
            threading.Thread(target=_shutdown, daemon=True).start()
        else:
            self.send_response(404)
            self.end_headers()


def _shutdown():
    global _server
    time.sleep(0.2)
    if _server:
        _server.shutdown()


def start_visualize(db_path: str) -> None:
    """
    Start the dashboard server, open browser, block until user exits.
    Called from cli.py — returns when server shuts down.
    """
    global _server

    html_path = Path(__file__).parent / "dashboard.html"
    if not html_path.exists():
        print(f"  Error: dashboard.html not found at {html_path}")
        return

    dashboard_html = html_path.read_text(encoding="utf-8")

    _Handler.db_path       = db_path
    _Handler.dashboard_html = dashboard_html

    _server = HTTPServer(("127.0.0.1", PORT), _Handler)

    url = f"http://127.0.0.1:{PORT}"
    print(f"\n  {url}  —  opening dashboard...")
    print(f"  Click 'EXIT' in the browser to return to the CLI.\n")

    # Open browser after brief delay so server is ready
    threading.Timer(0.4, lambda: webbrowser.open(url)).start()

    try:
        _server.serve_forever()
    except Exception:
        pass
    finally:
        _server = None

    from app.util.display import Colors as C
    print(f"\n{C.DIM}  Dashboard closed. Back to OptionsCLI.{C.RESET}\n")