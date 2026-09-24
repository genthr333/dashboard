import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs

import production

_cache = {"data": None, "timestamp": 0}
_cache_lock = threading.Lock()

SOURCES = ("signoz", "kuma", "matomo", "superset")

CATALOG = (
    ("payment", "Payment Gateway", "Platform", 1240, 0.0324, 60000, 0.9972),
    ("portal", "Portal Layanan", "Web Services", 680, 0.0042, 180000, 0.9995),
    ("identity", "Identity & SSO", "Security", 142, 0.0002, 240000, 0.9999),
    ("mobile", "Aplikasi Mobile API", "Digital Product", 218, 0.0008, 300000, 0.9998),
    ("documents", "Document Management", "Enterprise Apps", 186, 0.0003, 100000, 1),
    ("notification", "Notification Service", "Platform", 94, 0.0005, 160000, 0.9997),
    ("reporting", "Data & Reporting", "Data Office", 324, 0.0006, 40000, 0.9999),
    ("website", "Public Website", "Communications", 126, 0.0001, 200000, 1),
)


def mode():
    return os.getenv("DATA_MODE", "simulation")


def iso(t):
    return t.isoformat().replace("+00:00", "Z")


def adapter(source, now):
    """Simulation-mode adapter. Not reconstructed; only DATA_MODE=production is supported here."""
    raise NotImplementedError("Simulation mode not reconstructed; use DATA_MODE=production")


def aggregate(fail, stale, now=None):
    now = now or datetime.now(timezone.utc)
    live = mode() == "production"
    catalog = (
        [(a["id"], a["name"], a["owner"], None) for a in production.config()["applications"]]
        if live else CATALOG
    )

    def collect(source):
        if source == fail:
            raise ConnectionError("Simulated upstream unavailable")
        try:
            data = production.adapter(source, now) if live else adapter(source, now)
            is_stale = source == stale
            return source, {
                "status": "stale" if is_stale else "ok",
                "mode": mode(),
                "observedAt": iso(now - timedelta(hours=1) if is_stale else now),
                "error": None,
                "data": data if not is_stale else None,
            }
        except production.ConfigurationError:
            return source, {
                "status": "not_configured", "mode": mode(), "observedAt": None,
                "error": {"code": "NOT_CONFIGURED", "message": "Konfigurasi sumber belum lengkap"},
                "data": None,
            }
        except Exception:
            return source, {
                "status": "error", "mode": mode(), "observedAt": None,
                "error": {"code": "SOURCE_UNAVAILABLE", "message": "Sumber tidak tersedia; periksa endpoint, kredensial dan pemetaan respons"},
                "data": None,
            }

    with ThreadPoolExecutor(max_workers=4) as pool:
        sources = dict(pool.map(collect, SOURCES))

    s = sources["signoz"]["data"]
    k = sources["kuma"]["data"]
    m = sources["matomo"]["data"]
    b = sources["superset"]["data"]

    apps = []
    for key, name, owner, _ in catalog:
        perf = s["services"].get(key) if s else None
        mon = k["monitors"].get(key) if k else None
        rate = (perf["errorCount"] / perf["requestCount"]) if (perf and perf["requestCount"]) else None

        rag = "unknown"
        # CHANGED: status color now reflects the CURRENT up/down state only.
        # uptimeMtd (historical rolling average) still displays in the table,
        # but no longer participates in red/amber/green classification --
        # matches standard status-page practice (current status vs. historical
        # SLA percentage are shown separately, not blended into one number).
        if perf and mon and rate is not None and mon["up"] is not None:
            if not mon["up"] or perf["p95Ms"] >= 2000 or rate >= 0.05:
                rag = "red"
            elif perf["p95Ms"] >= 1500 or rate >= 0.02:
                rag = "amber"
            else:
                rag = "green"

        apps.append({
            "id": key,
            "name": name,
            "owner": owner,
            "rag": rag,
            "liveUptime": (100.0 if mon["up"] else 0.0) if (mon and mon["up"] is not None) else None,
            "uptimeMtd": mon["uptimeMtd"] if mon else None,
            "p95Ms": perf["p95Ms"] if perf else None,
            "errorRate": rate if perf else None,
            "requestCount": perf["requestCount"] if perf else None,
        })

    counts = {"green": 0, "amber": 0, "red": 0, "unknown": 0}
    for a in apps:
        counts[a["rag"]] += 1

    total = 0
    errors = 0
    for key, name, owner, _ in catalog:
        perf = s["services"].get(key) if s else None
        if perf:
            total += perf["requestCount"]
            errors += perf["errorCount"]

    metrics = {
        "healthRatio": (counts["green"] / len(apps)) if apps and not counts["unknown"] else None,
        "availabilityMtd": (
            sum(a["uptimeMtd"] for a in apps if a["uptimeMtd"] is not None) / len(apps)
        ) if apps and any(a["uptimeMtd"] is not None for a in apps) else None,
        "p95Ms": s["globalP95Ms"] if s else None,
        "errorRate": (errors / total) if total else None,
        "requestCount": total,
        "errorCount": errors,
    }

    return {
        "schemaVersion": "1.0",
        "mode": mode(),
        "status": "ok" if all(v["status"] == "ok" for v in sources.values()) else "partial",
        "generatedAt": iso(now),
        "timezone": "Asia/Jakarta",
        "refreshAfterSeconds": 60,
        "windows": {
            "operations": {"from": iso(now - timedelta(hours=24)), "to": iso(now)},
            "availability": "month_to_date",
            "analytics": "today_Matomo_site_timezone",
            "business": "today_Asia/Jakarta",
        },
        "sources": {k2: {kk: vv for kk, vv in v.items() if kk != "data"} for k2, v in sources.items()},
        "metrics": metrics,
        "healthCounts": counts,
        "applications": apps,
        "incidents": [
            {
                "appId": a["id"],
                "severity": "P1",
                "summary": f"{a['name']} berstatus kritis",
                "owner": a["owner"],
                "state": "Aktif",
                "startedAt": iso(now),
            }
            for a in apps if a["rag"] == "red"
        ] or None,
        "performanceTrend": s["trend"] if s else None,
        "analytics": m,
        "business": b,
        "definitions": {
            "health": "green / all applications; null when unknown exists",
            "availability": "equal-weight mean of application uptime MTD",
            "errorRate": "sum(errorCount) / sum(requestCount)",
            "p95": "global request distribution quantile; null if not configured",
            "missing": "null, never zero or healthy",
        },
    }


DIST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dist")

MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
}


class Handler(BaseHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_json(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (ConnectionAbortedError, BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        parsed = urlsplit(self.path)
        qs = parse_qs(parsed.query)

        if parsed.path == "/healthz":
            self.send_json({"status": "ok"})
            return
        if parsed.path == "/api/v1/overview":

            allowed = {"signoz", "kuma", "matomo", "superset"}
            fail = qs.get("fail", [None])[0]
            stale = qs.get("stale", [None])[0]
            unknown_params = set(qs.keys()) - {"fail", "stale"}
            if unknown_params or (fail and fail not in allowed) or (stale and stale not in allowed):
                self.send_json({"error": "Bad request"}, status=400)
                return
            if mode() == "production" and (fail or stale):
                self.send_json({"error": "fail/stale not allowed in production"}, status=400)
                return
            try:
                with _cache_lock:
                    now_ts = time.time()
                    if _cache["data"] and (now_ts - _cache["timestamp"]) < 45 and not fail and not stale:
                        result = _cache["data"]
                    else:
                        result = aggregate(fail, stale)
                        _cache["data"] = result
                        if not fail and not stale:
                            _cache["timestamp"] = now_ts
                self.send_json(result)
            except Exception as e:
                import traceback
                traceback.print_exc()
                try:
                    self.send_json({"error": str(e)}, status=500)
                except (ConnectionAbortedError, BrokenPipeError, ConnectionResetError):
                    pass
            return

        rel = parsed.path.lstrip("/") or "index.html"
        file_path = os.path.normpath(os.path.join(DIST_DIR, rel))
        if not file_path.startswith(os.path.normpath(DIST_DIR)):
            self.send_json({"error": "Not found"}, status=404)
            return
        if not os.path.isfile(file_path):
            self.send_json({"error": "Not found"}, status=404)
            return
        ext = os.path.splitext(file_path)[1]
        with open(file_path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", MIME_TYPES.get(ext, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        self.send_json({"error": "Method not allowed"}, status=405)

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} - - [{self.log_date_time_string()}] {fmt % args}")


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8766"))
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"Observatory {mode()}: http://{host}:{port}")
    httpd.serve_forever()