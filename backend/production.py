import json
import math
import os
import ssl
from pathlib import Path
from urllib.parse import urlsplit, urlencode
from urllib.request import Request, urlopen, HTTPRedirectHandler, HTTPSHandler, build_opener


class ConfigurationError(Exception):
    pass


class ResponseError(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ResponseError("UPSTREAM_REDIRECT_BLOCKED")


def config():
    p = os.getenv("PRODUCTION_CONFIG")
    if not p:
        raise ConfigurationError("Set PRODUCTION_CONFIG")
    d = json.loads(Path(p).read_text())
    apps = d.get("applications", [])
    if apps and (len(apps) > 50 or len({a["id"] for a in apps}) != len(apps)):
        raise ConfigurationError("Invalid applications")
    return d


def secret(name):
    v = os.getenv(name)
    if not v:
        raise ConfigurationError("Missing credential")
    return v


def request(base, path, headers=None, body=None, form=None):
    u = urlsplit(base)
    if u.scheme != "https" or not u.hostname or u.username or u.password or u.query or u.fragment:
        raise ConfigurationError("HTTPS origin required")

    url = base.rstrip("/") + path
    hdrs = dict(headers or {})
    data = None

    if form is not None:
        data = urlencode(form).encode()
        hdrs.setdefault("Content-Type", "application/x-www-form-urlencoded")
    elif body is not None:
        data = json.dumps(body).encode()
        hdrs.setdefault("Content-Type", "application/json")

    req = Request(url, data=data, headers=hdrs, method="POST" if data is not None else "GET")

    ctx = ssl.create_default_context(cafile=os.getenv("UPSTREAM_CA_FILE"))
    opener = build_opener(NoRedirect, HTTPSHandler(context=ctx))

    try:
        with opener.open(req, timeout=8) as resp:
            raw = resp.read(4 * 1024 * 1024 + 1)
            if len(raw) > 4 * 1024 * 1024:
                raise ResponseError("RESPONSE_TOO_LARGE")
            if resp.status != 200:
                raise ResponseError(f"HTTP_{resp.status}")
            return json.loads(raw)
    except ResponseError:
        raise
    except Exception as e:
        raise ResponseError(f"REQUEST_FAILED: {e}")


def pointer(data, path):
    if not (isinstance(path, str) and path.startswith("/")):
        raise ConfigurationError("Set JSON pointer")
    for part in path[1:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        data = data[int(part)] if isinstance(data, list) else data[part]
    return data


def number(value, ratio=False):
    if isinstance(value, bool):
        raise ResponseError("INVALID_NUMBER")
    v = float(value)
    if not (math.isfinite(v) and v >= 0 and (not ratio or v <= 1)):
        raise ResponseError("INVALID_NUMBER")
    return v


def query_metric(source, spec, now):
    if not spec:
        return None
    body = json.dumps(spec["body"])
    body = body.replace('"$START_MS"', str(int((now - __import__("datetime").timedelta(hours=24)).timestamp() * 1000)))
    body = body.replace('"$END_MS"', str(int(now.timestamp() * 1000)))
    headers = {"SIGNOZ-API-KEY": secret("SIGNOZ_API_KEY")} if source == "signoz" else {}
    path = "/api/v5/query_range" if source == "signoz" else "/api/v1/chart/data"
    result = request(secret(f"{source.upper()}_URL"), path, headers=headers, body=json.loads(body))
    v = pointer(result, spec["valuePointer"])
    v = number(v)
    return v * spec.get("scale", 1)


def prom(spec, now):
    if not spec:
        return None
    headers = {}
    token = os.getenv("PROMETHEUS_BEARER_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    result = request(
        secret("PROMETHEUS_URL"),
        "/api/v1/query?" + urlencode({"query": spec, "time": now.timestamp()}),
        headers=headers,
    )
    return float(result["data"]["result"][0]["value"][1])


def signoz_trend(spec, now):
    if not spec:
        return None
    body = json.dumps(spec["body"])
    body = body.replace('"$START_MS"', str(int((now - __import__("datetime").timedelta(hours=24)).timestamp() * 1000)))
    body = body.replace('"$END_MS"', str(int(now.timestamp() * 1000)))
    headers = {"SIGNOZ-API-KEY": secret("SIGNOZ_API_KEY")}
    result = request(secret("SIGNOZ_URL"), "/api/v5/query_range", headers=headers, body=json.loads(body))

    try:
        results = result["data"]["data"]["results"]
        by_name = {r["queryName"]: r["aggregations"][0]["series"][0]["values"] for r in results}
        p95_series = by_name.get("A", [])
        err_series = {pt["timestamp"]: pt["value"] for pt in by_name.get("B", [])}
        total_series = {pt["timestamp"]: pt["value"] for pt in by_name.get("C", [])}

        points = []
        for pt in sorted(p95_series, key=lambda x: x["timestamp"]):
            ts = pt["timestamp"]
            p95_ms = float(pt["value"]) * spec.get("p95Scale", 0.000001)
            total = total_series.get(ts, 0)
            errs = err_series.get(ts, 0)
            err_rate = (errs / total) if total else 0.0
            points.append({"p95Ms": p95_ms, "errorRate": err_rate})
    except (KeyError, IndexError, TypeError):
        return None
    return points or None


def adapter(source, now):
    cfg = config()
    c = cfg.get(source, {})
    if not c.get("enabled"):
        raise ConfigurationError("Source not configured")

    if source == "kuma":
        monitors = {}
        for app in cfg["applications"]:
            q = c.get("applications", {}).get(app["id"])
            if not q:
                continue
            up = prom(q.get("currentStatusQuery"), now)
            uptime = prom(q.get("uptimeMtdQuery"), now)
            monitors[app["id"]] = {
                "up": bool(up) if up in (0, 1) else None,
                "uptimeMtd": number(uptime, ratio=True) if uptime is not None else None,
            }
        if not monitors:
            raise ConfigurationError("No monitor queries configured")
        return {"monitors": monitors}

    if source == "matomo":
        def report(method):
            d = request(secret("MATOMO_URL"), "/index.php", form={
                "module": "API",
                "method": method,
                "idSite": str(c["siteId"]),
                "period": "day",
                "date": "today",
                "format": "JSON",
                "token_auth": secret("MATOMO_TOKEN_AUTH"),
                "format_metrics": "0",
            })
            if d.get("result") == "error":
                raise ResponseError("MATOMO_REPORT_FAILED")
            return d

        visits = report("VisitsSummary.get")
        actions = report("Actions.get")
        count = number(visits["nb_visits"])
        return {
            "uniqueVisitors": number(visits["nb_uniq_visitors"]) if "nb_uniq_visitors" in visits else None,
            "pageViews": number(actions["nb_pageviews"]),
            "bounceRate": (number(visits["bounce_count"]) / count) if count else None,
            "averageSessionSeconds": (number(visits["sum_visit_length"]) / count) if count else None,
            "hourlyVisits": [],
        }

    if source == "signoz":
        services = {}
        for app in cfg["applications"]:
            q = c.get("applications", {}).get(app["id"])
            if not q:
                continue
            values = {key: query_metric("signoz", q.get(key), now) for key in ("p95Ms", "requestCount", "errorCount")}
            if any(v is None for v in values.values()):
                continue
            services[app["id"]] = values
        if not services:
            raise ConfigurationError("No service queries configured")
        return {
            "services": services,
            "globalP95Ms": query_metric("signoz", c.get("globalP95Ms"), now),
            "trend": signoz_trend(c.get("trend"), now),  # CHANGED: was hardcoded None
            "incidents": None,  # still unimplemented, see note below
        }

    if source == "superset":
        fields = ("successfulTransactions", "targetTransactions", "transactionValueIdr", "conversionRate", "pendingTransactions")
        result = {k: query_metric(source, c.get(k), now) for k in fields}
        if not any(result.values()):
            raise ConfigurationError("No KPI queries configured")
        if result["conversionRate"] is not None:
            number(result["conversionRate"], ratio=True)
        return result

    raise ConfigurationError("Unknown source")
