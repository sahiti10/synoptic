"""
server.py
---------
A real-time local web server for Synoptic, built entirely on the Python
standard library (`http.server`, `threading`, `json`) -- no Flask, no
FastAPI, no `pip install`.

What it does:
  - Runs the ETL pipeline once at startup, then again on a background
    timer (config.REFRESH_INTERVAL_SECONDS), so alert data stays current
    without the user re-running anything.
  - Serves a small JSON API (`/api/alerts`, `/api/status`,
    `/api/states-geojson`, `/api/refresh`) consumed by the frontend in
    static/app.js, which polls for updates and re-renders live.
  - Serves the static frontend (static/index.html, style.css, app.js,
    manifest.json, sw.js) so the whole thing is one process, one command.

Run with:  python -m src.server   (or `python main.py --serve`)
Then open: http://127.0.0.1:8765
"""

import json
import os
import re
import threading
import time
import datetime as dt
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from config import (
    SERVER_HOST, SERVER_PORT, REFRESH_INTERVAL_SECONDS,
    STATIC_DIR, US_STATES_GEOJSON_PATH,
)
from src import db, etl_pipeline, spatial_utils
from src.us_states_meta import STATE_ABBR_TO_NAME, KNOWN_LOCATIONS

# ---------------------------------------------------------------------------
# In-memory shared state (guarded by _lock). The background refresh thread
# writes here; request handlers read from here -- so API responses are
# instant and never block on a live NWS/Mastodon call.
# ---------------------------------------------------------------------------
_lock = threading.RLock()
_state = {
    "alerts": [],              # enriched alert dicts, see _enrich_alert()
    "last_updated": None,      # ISO8601 string
    "refreshing": False,
    "error": None,
    "newly_severe_ids": [],    # ids that became Severe/Extreme on the latest refresh
    "interval_seconds": REFRESH_INTERVAL_SECONDS,
}

_AREA_STATE_RE = re.compile(r",\s*([A-Z]{2})\b")


def _parse_states_from_area_desc(area_desc: str):
    """'Travis, TX; Harris, TX' -> ['TX']  (order-preserving, deduped)"""
    if not area_desc:
        return []
    found = _AREA_STATE_RE.findall(area_desc)
    seen = []
    for code in found:
        if code in STATE_ABBR_TO_NAME and code not in seen:
            seen.append(code)
    return seen


def _enrich_alert(row: dict, outage_by_id: dict) -> dict:
    """Turn a raw `alerts` table row into what the frontend needs."""
    geometry = db.geometry_from_row(row)
    centroid = None
    if geometry:
        try:
            lon, lat = spatial_utils.geometry_centroid(geometry)
            centroid = {"lon": lon, "lat": lat}
        except Exception:
            centroid = None

    states = _parse_states_from_area_desc(row.get("area_desc") or "")
    outage = outage_by_id.get(row["id"], {})

    return {
        "id": row["id"],
        "event": row.get("event"),
        "severity": row.get("severity") or "Unknown",
        "certainty": row.get("certainty"),
        "urgency": row.get("urgency"),
        "headline": row.get("headline"),
        "description": row.get("description"),
        "area_desc": row.get("area_desc"),
        "states": states,
        "state_names": [STATE_ABBR_TO_NAME[s] for s in states],
        "sent": row.get("sent"),
        "effective": row.get("effective"),
        "expires": row.get("expires"),
        "geometry": geometry,
        "centroid": centroid,
        "risk_score": outage.get("risk_score"),
        "simulated_customers_out": outage.get("simulated_customers_out"),
    }


_SEVERITY_RANK = {"Extreme": 4, "Severe": 3, "Moderate": 2, "Minor": 1, "Unknown": 0}


def refresh_once(states=None, hashtags=None):
    """Run the ETL pipeline, then rebuild the in-memory alert cache."""
    with _lock:
        _state["refreshing"] = True
        _state["error"] = None

    previous_ids_high_severity = {
        a["id"] for a in _state["alerts"] if _SEVERITY_RANK.get(a["severity"], 0) >= 3
    }

    try:
        etl_pipeline.run(states=states, hashtags=hashtags, verbose=False)

        with db.get_connection() as conn:
            alert_rows = db.fetch_all(conn, "SELECT * FROM alerts ORDER BY sent DESC")
            outage_rows = db.fetch_all(conn, "SELECT * FROM outage_simulation")
        outage_by_id = {o["alert_id"]: o for o in outage_rows}

        enriched = [_enrich_alert(r, outage_by_id) for r in alert_rows]
        enriched.sort(key=lambda a: _SEVERITY_RANK.get(a["severity"], 0), reverse=True)

        new_high_severity_ids = [
            a["id"] for a in enriched
            if _SEVERITY_RANK.get(a["severity"], 0) >= 3 and a["id"] not in previous_ids_high_severity
        ]

        with _lock:
            _state["alerts"] = enriched
            _state["last_updated"] = dt.datetime.utcnow().isoformat() + "Z"
            _state["newly_severe_ids"] = new_high_severity_ids
            _state["refreshing"] = False
    except Exception as e:
        with _lock:
            _state["error"] = str(e)
            _state["refreshing"] = False


def _background_loop(states=None, hashtags=None):
    while True:
        time.sleep(REFRESH_INTERVAL_SECONDS)
        refresh_once(states=states, hashtags=hashtags)


def start_background_refresh(states=None, hashtags=None):
    thread = threading.Thread(target=_background_loop, args=(states, hashtags), daemon=True)
    thread.start()


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------
_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".webmanifest": "application/manifest+json",
}


class SynopticHandler(BaseHTTPRequestHandler):
    server_version = "SynopticHTTP/1.0"

    def log_message(self, fmt, *args):
        pass  # keep console output clean; ETL logging covers activity

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path, content_type):
        try:
            with open(path, "rb") as f:
                body = f.read()
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        route = parsed.path
        query = parse_qs(parsed.query)

        if route == "/api/alerts":
            with _lock:
                self._send_json({"alerts": _state["alerts"], "last_updated": _state["last_updated"]})
            return

        if route == "/api/status":
            with _lock:
                self._send_json({
                    "last_updated": _state["last_updated"],
                    "refreshing": _state["refreshing"],
                    "error": _state["error"],
                    "alert_count": len(_state["alerts"]),
                    "interval_seconds": _state["interval_seconds"],
                    "newly_severe_ids": _state["newly_severe_ids"],
                })
            return

        if route == "/api/locations":
            self._send_json({
                "locations": [
                    {"label": label, "state": state, "lat": lat, "lon": lon}
                    for (label, state, lat, lon) in KNOWN_LOCATIONS
                ]
            })
            return

        if route == "/api/states-geojson":
            self._send_file(US_STATES_GEOJSON_PATH, "application/json; charset=utf-8")
            return

        if route == "/api/refresh":
            threading.Thread(target=refresh_once, daemon=True).start()
            self._send_json({"status": "refresh started"}, status=202)
            return

        # static file serving
        rel_path = route.lstrip("/")
        if rel_path == "" or rel_path == "/":
            rel_path = "index.html"
        file_path = os.path.normpath(os.path.join(STATIC_DIR, rel_path))
        if not file_path.startswith(os.path.normpath(STATIC_DIR)):
            self.send_response(403)
            self.end_headers()
            return
        ext = os.path.splitext(file_path)[1]
        content_type = _CONTENT_TYPES.get(ext, "application/octet-stream")
        self._send_file(file_path, content_type)

    def do_POST(self):
        # /api/refresh also accepts POST, same behavior as GET
        if urlparse(self.path).path == "/api/refresh":
            self.do_GET()
            return
        self.send_response(404)
        self.end_headers()


def run(states=None, hashtags=None, open_browser=True):
    print("=" * 60)
    print("Synoptic — real-time server")
    print("=" * 60)
    print("[server] Running initial data fetch (this can take a few seconds)...")
    refresh_once(states=states, hashtags=hashtags)
    if _state["error"]:
        print(f"[server] Initial fetch had an issue: {_state['error']}")
        print("[server] Starting anyway — the background refresh will keep retrying.")

    start_background_refresh(states=states, hashtags=hashtags)

    httpd = ThreadingHTTPServer((SERVER_HOST, SERVER_PORT), SynopticHandler)
    url = f"http://{SERVER_HOST}:{SERVER_PORT}"
    print(f"[server] Serving on {url}")
    print(f"[server] Auto-refreshing every {REFRESH_INTERVAL_SECONDS}s. Press Ctrl+C to stop.")

    if open_browser:
        import webbrowser
        threading.Timer(0.7, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[server] Shutting down.")
        httpd.shutdown()


if __name__ == "__main__":
    run()
