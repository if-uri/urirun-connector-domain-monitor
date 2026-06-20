# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

from __future__ import annotations

import json
import os
import socket
import sqlite3
import time
import urllib.error
import urllib.request
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import urirun


CONNECTOR_ID = "domain-monitor"
MONITOR = urirun.connector(CONNECTOR_ID, scheme="monitor")
BROWSER = urirun.connector(CONNECTOR_ID, scheme="browser")
LOG = urirun.connector(CONNECTOR_ID, scheme="log")
FLOW = urirun.connector(CONNECTOR_ID, scheme="flow")
DEFAULT_DB = "~/.urirun/host.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS datasets (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  description TEXT NOT NULL DEFAULT '',
  schema_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS records (
  id TEXT PRIMARY KEY,
  dataset_id TEXT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
  key TEXT NOT NULL,
  data_json TEXT NOT NULL,
  source_uri TEXT,
  confidence REAL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(dataset_id, key)
);

CREATE TABLE IF NOT EXISTS artifacts (
  id TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  uri TEXT NOT NULL UNIQUE,
  path TEXT,
  meta_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS checks (
  id TEXT PRIMARY KEY,
  subject TEXT NOT NULL,
  check_uri TEXT NOT NULL,
  status TEXT NOT NULL,
  result_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS logs (
  id TEXT PRIMARY KEY,
  stream TEXT NOT NULL,
  event TEXT NOT NULL,
  detail_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL
);
"""


def connector_manifest() -> dict[str, Any]:
    return urirun.load_manifest(__package__)


def _json_value(value: Any, default: Any):
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    return json.loads(str(value))


def _bool(value: Any, default: bool = False) -> bool:
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _int_or_none(value: Any) -> int | None:
    if value in (None, "", 0, "0"):
        return None
    return int(value)


def now_id() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def db_path(path: str | None = None) -> Path:
    return Path(path or os.getenv("URIRUN_HOST_DB", DEFAULT_DB)).expanduser()


def connect(path: str | None = None) -> sqlite3.Connection:
    resolved = db_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(resolved))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def connection(path: str | None = None):
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def row_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    data = dict(row)
    for key in ("schema_json", "data_json", "meta_json", "result_json", "detail_json"):
        if key in data and data[key] is not None:
            try:
                data[key.removesuffix("_json")] = json.loads(data.pop(key))
            except json.JSONDecodeError:
                pass
    return data


def rows_dict(rows) -> list[dict]:
    return [row_dict(row) for row in rows]


def init_db(path: str | None = None) -> dict[str, Any]:
    with connection(path) as conn:
        conn.executescript(SCHEMA)
    return {"ok": True, "path": str(db_path(path))}


def register_artifact(path: str | None, kind: str, uri: str, artifact_path: str | None = None, meta: dict | None = None) -> dict:
    init_db(path)
    artifact_id = new_id("art")
    with connection(path) as conn:
        conn.execute(
            """
            INSERT INTO artifacts(id, kind, uri, path, meta_json, created_at)
            VALUES(?, ?, ?, ?, ?, ?)
            ON CONFLICT(uri) DO UPDATE SET kind=excluded.kind, path=excluded.path, meta_json=excluded.meta_json
            """,
            (artifact_id, kind, uri, artifact_path, json.dumps(meta or {}, sort_keys=True), now_iso()),
        )
        return row_dict(conn.execute("SELECT * FROM artifacts WHERE uri = ?", (uri,)).fetchone())


def add_check(path: str | None, subject: str, check_uri: str, status: str, result: dict | None = None) -> dict:
    init_db(path)
    check_id = new_id("chk")
    with connection(path) as conn:
        conn.execute(
            "INSERT INTO checks(id, subject, check_uri, status, result_json, created_at) VALUES(?, ?, ?, ?, ?, ?)",
            (check_id, subject, check_uri, status, json.dumps(result or {}, sort_keys=True), now_iso()),
        )
        return row_dict(conn.execute("SELECT * FROM checks WHERE id = ?", (check_id,)).fetchone())


def recent_checks(path: str | None = None, subject: str | None = None, limit: int = 20) -> list[dict]:
    init_db(path)
    params: list[Any] = []
    sql = "SELECT * FROM checks"
    if subject:
        sql += " WHERE subject = ?"
        params.append(subject)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with connection(path) as conn:
        return rows_dict(conn.execute(sql, params).fetchall())


def add_log(path: str | None, stream: str, event: str, detail: dict | None = None) -> dict:
    init_db(path)
    log_id = new_id("log")
    with connection(path) as conn:
        conn.execute(
            "INSERT INTO logs(id, stream, event, detail_json, created_at) VALUES(?, ?, ?, ?, ?)",
            (log_id, stream, event, json.dumps(detail or {}, sort_keys=True), now_iso()),
        )
        return row_dict(conn.execute("SELECT * FROM logs WHERE id = ?", (log_id,)).fetchone())


def recent_logs(path: str | None = None, stream: str | None = None, limit: int = 20) -> list[dict]:
    init_db(path)
    params: list[Any] = []
    sql = "SELECT * FROM logs"
    if stream:
        sql += " WHERE stream = ?"
        params.append(stream)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with connection(path) as conn:
        return rows_dict(conn.execute(sql, params).fetchall())


def search_records(path: str | None, query: str = "", dataset: str | None = None, limit: int = 20) -> list[dict]:
    init_db(path)
    params: list[Any] = []
    where = []
    if dataset:
        where.append("d.name = ?")
        params.append(dataset)
    if query:
        where.append("(r.key LIKE ? OR r.data_json LIKE ? OR COALESCE(r.source_uri, '') LIKE ?)")
        needle = f"%{query}%"
        params.extend([needle, needle, needle])
    sql = "SELECT r.*, d.name AS dataset_name FROM records r JOIN datasets d ON d.id = r.dataset_id"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY r.updated_at DESC LIMIT ?"
    params.append(limit)
    with connection(path) as conn:
        return rows_dict(conn.execute(sql, params).fetchall())


def default_url(domain: str) -> str:
    return domain if domain.startswith(("http://", "https://")) else f"https://{domain}"


def probe_http_status(url: str, timeout: float = 10.0, expected_status: int | None = None) -> dict[str, Any]:
    started = time.monotonic()
    request = urllib.request.Request(url, headers={"User-Agent": "urirun-domain-monitor/0.2"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(response.status)
            ok = status == expected_status if expected_status is not None else status < 400
            return {
                "ok": ok,
                "url": url,
                "status": status,
                "elapsedMs": int((time.monotonic() - started) * 1000),
                "headers": dict(response.headers.items()),
            }
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        ok = status == expected_status if expected_status is not None else status < 400
        return {"ok": ok, "url": url, "status": status, "elapsedMs": int((time.monotonic() - started) * 1000), "error": str(exc)}
    except OSError as exc:
        return {"ok": False, "url": url, "status": None, "elapsedMs": int((time.monotonic() - started) * 1000), "error": str(exc)}


def resolve_dns_records(domain: str, record_types: list[str] | None = None) -> dict[str, Any]:
    requested = {item.upper() for item in (record_types or ["A", "AAAA"])}
    records = {"A": [], "AAAA": []}
    try:
        infos = socket.getaddrinfo(domain, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        return {"ok": False, "domain": domain, "records": records, "error": str(exc), "provider": "system-resolver"}

    for family, _kind, _proto, _canon, sockaddr in infos:
        if family == socket.AF_INET and "A" in requested:
            records["A"].append(sockaddr[0])
        elif family == socket.AF_INET6 and "AAAA" in requested:
            records["AAAA"].append(sockaddr[0])
    normalized = {key: sorted(set(value)) for key, value in records.items() if key in requested}
    return {"ok": True, "domain": domain, "records": normalized, "provider": "system-resolver"}


def expected_records_from_payload(payload: dict[str, Any]) -> dict[str, list[str]]:
    expected = payload.get("expected_records") or payload.get("expected") or {}
    if not isinstance(expected, dict):
        expected = {"A": _split_csv(expected)}
    if payload.get("expected_a") is not None:
        expected["A"] = _split_csv(payload.get("expected_a"))
    if payload.get("expected_aaaa") is not None:
        expected["AAAA"] = _split_csv(payload.get("expected_aaaa"))
    return {str(key).upper(): _split_csv(value) for key, value in expected.items() if _split_csv(value)}


def dns_mismatches(current: dict[str, Any], expected: dict[str, list[str]]) -> list[dict[str, Any]]:
    records = current.get("records") or {}
    mismatches = []
    for record_type, expected_values in expected.items():
        actual_values = _split_csv(records.get(record_type))
        if actual_values != expected_values:
            mismatches.append({"type": record_type, "expected": expected_values, "actual": actual_values})
    return mismatches


def capture_screenshot_artifact(
    *,
    db: str | None,
    domain: str,
    url: str,
    out_dir: str | None = None,
    reason: str = "failure",
    meta: dict | None = None,
) -> dict:
    timestamp = now_id()
    directory = Path(out_dir or "~/.urirun/artifacts/screenshots").expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{domain}-{timestamp}.screenshot.json"
    content = {"domain": domain, "url": url, "reason": reason, "createdAt": timestamp, "meta": meta or {}}
    path.write_text(json.dumps(content, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    artifact_uri = f"artifact://host/screenshot/{domain}/{timestamp}"
    return register_artifact(db, "screenshot", artifact_uri, str(path), content)


def create_dns_repair_ticket(
    *,
    project: str,
    domain: str,
    current: dict[str, Any],
    expected: dict[str, Any],
    mismatches: list[dict[str, Any]],
) -> dict[str, Any]:
    prompt = (
        f"Review DNS mismatch for {domain}. "
        f"Expected={json.dumps(expected, sort_keys=True)} "
        f"Current={json.dumps(current.get('records') or {}, sort_keys=True)}. "
        "Prepare a safe DNS plan only; do not apply changes automatically."
    )
    try:
        from urirun_connector_planfile import create_ticket
    except ImportError:
        return {
            "ok": False,
            "skipped": True,
            "reason": "urirun-connector-planfile is not installed",
            "prompt": prompt,
            "domain": domain,
            "mismatches": mismatches,
        }
    return create_ticket(
        project=project,
        name=f"Review DNS mismatch: {domain}",
        description=prompt,
        priority="high",
        labels="domain,dns,repair,review",
        queue="review",
        executor_handler="dns://host/records/command/plan",
        prompt=prompt,
    )


def check_domain(
    *,
    domain: str,
    url: str | None = None,
    expected: dict[str, list[str]] | None = None,
    db: str | None = None,
    project: str | None = None,
    execute: bool = False,
    timeout: float = 10.0,
    screenshot_when: str = "failure",
    screenshot_dir: str | None = None,
    create_repair_ticket: bool = True,
) -> dict[str, Any]:
    target_url = url or default_url(domain)
    http = probe_http_status(target_url, timeout=timeout)
    dns = resolve_dns_records(domain, sorted((expected or {"A": []}).keys()) if expected else None)
    mismatches = dns_mismatches(dns, expected or {})
    ok = bool(http.get("ok")) and bool(dns.get("ok")) and not mismatches
    result: dict[str, Any] = {
        "ok": ok,
        "domain": domain,
        "url": target_url,
        "http": http,
        "dns": dns,
        "dnsMismatches": mismatches,
        "executed": execute,
        "artifacts": [],
        "tickets": [],
    }
    if not execute:
        return result

    result["check"] = add_check(db, domain, f"monitor://{domain}/domain/command/check", "ok" if ok else "failed", {"http": http, "dns": dns, "dnsMismatches": mismatches})
    if not ok and screenshot_when in {"failure", "always"}:
        result["artifacts"].append(capture_screenshot_artifact(db=db, domain=domain, url=target_url, out_dir=screenshot_dir, reason="failure", meta={"http": http, "dns": dns, "dnsMismatches": mismatches}))
    elif screenshot_when == "always":
        result["artifacts"].append(capture_screenshot_artifact(db=db, domain=domain, url=target_url, out_dir=screenshot_dir, reason="manual"))

    if mismatches and project and create_repair_ticket:
        result["tickets"].append(create_dns_repair_ticket(project=project, domain=domain, current=dns, expected=expected or {}, mismatches=mismatches))

    result["log"] = add_log(db, "daily", "daily_domain_check.finished", {"domain": domain, "ok": ok, "httpStatus": http.get("status"), "dnsMismatches": mismatches})
    return result


def run_daily(
    *,
    db: str | None,
    project: str | None,
    execute: bool,
    dataset: str = "domains",
    limit: int = 50,
    screenshot_when: str = "failure",
    screenshot_dir: str | None = None,
) -> dict[str, Any]:
    records = search_records(db, "", dataset=dataset, limit=limit)
    results = []
    for record in records:
        data = record.get("data") or {}
        domain = data.get("domain") or record.get("key")
        if not domain:
            continue
        results.append(
            check_domain(
                domain=str(domain),
                url=data.get("url"),
                expected=expected_records_from_payload(data),
                db=db,
                project=project,
                execute=execute,
                timeout=float(data.get("timeout", 10.0)),
                screenshot_when=screenshot_when,
                screenshot_dir=screenshot_dir,
            )
        )
    return {"ok": all(item.get("ok") for item in results), "count": len(results), "results": results, "executed": execute}


def _expected_payload(expected_records: str = "", expected_a: str = "", expected_aaaa: str = "") -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if expected_records:
        payload["expected_records"] = _json_value(expected_records, {})
    if expected_a:
        payload["expected_a"] = expected_a
    if expected_aaaa:
        payload["expected_aaaa"] = expected_aaaa
    return payload


def _split_csv(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    return [item.strip() for item in str(value).split(",") if item.strip()]


def http_status(domain: str = "", url: str = "", timeout: float = 10.0, expected_status: int = 0) -> dict[str, Any]:
    target = domain or "localhost"
    check_url = url or default_url(target)
    result = probe_http_status(check_url, timeout=float(timeout), expected_status=_int_or_none(expected_status))
    return {"ok": bool(result.get("ok")), "connector": CONNECTOR_ID, "type": "domain-monitor", "domain": target, "http": result}


def dns_current(domain: str = "", provider: str = "", record_types: str = "", current_records: str = "", profile: str = "") -> dict[str, Any]:
    target = domain or "localhost"
    if current_records:
        return {
            "ok": True,
            "connector": CONNECTOR_ID,
            "type": "domain-monitor",
            "domain": target,
            "records": _json_value(current_records, []),
            "source": "payload",
            "profile": profile,
        }
    if provider:
        return {
            "ok": False,
            "connector": CONNECTOR_ID,
            "type": "domain-monitor",
            "domain": target,
            "error": f"provider={provider} is handled by a provider-specific connector",
        }
    result = resolve_dns_records(target, _split_csv(record_types) or None)
    return {"ok": bool(result.get("ok")), "connector": CONNECTOR_ID, "type": "domain-monitor", **result}


def dns_expected(expected_records: str = "", expected_a: str = "", expected_aaaa: str = "") -> dict[str, Any]:
    payload = _expected_payload(expected_records=expected_records, expected_a=expected_a, expected_aaaa=expected_aaaa)
    return {"ok": True, "connector": CONNECTOR_ID, "type": "domain-monitor", "expectedRecords": expected_records_from_payload(payload)}


def screenshot(domain: str = "", url: str = "", db: str = "", screenshot_dir: str = "", reason: str = "manual", meta: str = "") -> dict[str, Any]:
    target = domain or "localhost"
    artifact = capture_screenshot_artifact(
        db=db or None,
        domain=target,
        url=url or default_url(target),
        out_dir=screenshot_dir or None,
        reason=reason,
        meta=_json_value(meta, {}),
    )
    return {"ok": True, "connector": CONNECTOR_ID, "type": "domain-monitor", "artifact": artifact}


def log_write(stream: str = "daily", event: str = "", detail: str = "", db: str = "") -> dict[str, Any]:
    if not event:
        raise ValueError("event is required")
    log = add_log(db or None, stream, event, _json_value(detail, {}))
    return {"ok": True, "connector": CONNECTOR_ID, "type": "domain-monitor", "log": log}


def logs_recent(stream: str = "daily", limit: int = 20, db: str = "") -> dict[str, Any]:
    logs = recent_logs(db or None, stream=stream, limit=int(limit))
    return {"ok": True, "connector": CONNECTOR_ID, "type": "domain-monitor", "logs": logs}


def domain_check(
    domain: str = "",
    url: str = "",
    expected_records: str = "",
    expected_a: str = "",
    expected_aaaa: str = "",
    db: str = "",
    project: str = "",
    timeout: float = 10.0,
    screenshot_when: str = "failure",
    screenshot_dir: str = "",
    create_repair_ticket: bool = True,
    execute: bool = True,
) -> dict[str, Any]:
    payload = _expected_payload(expected_records=expected_records, expected_a=expected_a, expected_aaaa=expected_aaaa)
    expected = expected_records_from_payload(payload)
    result = check_domain(
        domain=domain or "localhost",
        url=url or None,
        expected=expected,
        db=db or None,
        project=project or None,
        execute=_bool(execute, True),
        timeout=float(timeout),
        screenshot_when=screenshot_when,
        screenshot_dir=screenshot_dir or None,
        create_repair_ticket=_bool(create_repair_ticket, True),
    )
    return {"connector": CONNECTOR_ID, "type": "domain-monitor", "flow": "domain-check", **result}


def daily_run(
    db: str = "",
    project: str = "",
    dataset: str = "domains",
    limit: int = 50,
    screenshot_when: str = "failure",
    screenshot_dir: str = "",
    execute: bool = True,
) -> dict[str, Any]:
    result = run_daily(
        db=db or None,
        project=project or None,
        execute=_bool(execute, True),
        dataset=dataset,
        limit=int(limit),
        screenshot_when=screenshot_when,
        screenshot_dir=screenshot_dir or None,
    )
    return {"connector": CONNECTOR_ID, "type": "domain-monitor", "flow": "daily-domain-run", **result}


def run_action(action: str, **kwargs: Any) -> dict[str, Any]:
    table = {
        "http-status": http_status,
        "dns-current": dns_current,
        "dns-expected": dns_expected,
        "screenshot": screenshot,
        "log-write": log_write,
        "logs-recent": logs_recent,
        "domain-check": domain_check,
        "daily-run": daily_run,
    }
    if action not in table:
        raise ValueError(f"unsupported action: {action}")
    return table[action](**kwargs)


@MONITOR.command("http/query/status", meta={"label": "HTTP status check"})
def http_status_command(domain: str = "", url: str = "", timeout: float = 10.0, expected_status: int = 0) -> list[str]:
    return ["urirun-domain-monitor", "http-status", "--domain", "{domain}", "--url", "{url}", "--timeout", "{timeout}", "--expected-status", "{expected_status}"]


@MONITOR.command("dns/query/current", meta={"label": "Current DNS records"})
def dns_current_command(domain: str = "", provider: str = "", record_types: str = "", current_records: str = "", profile: str = "") -> list[str]:
    return ["urirun-domain-monitor", "dns-current", "--domain", "{domain}", "--provider", "{provider}", "--record-types", "{record_types}", "--current-records", "{current_records}", "--profile", "{profile}"]


@MONITOR.command("dns/query/expected", meta={"label": "Expected DNS records"})
def dns_expected_command(expected_records: str = "", expected_a: str = "", expected_aaaa: str = "") -> list[str]:
    return ["urirun-domain-monitor", "dns-expected", "--expected-records", "{expected_records}", "--expected-a", "{expected_a}", "--expected-aaaa", "{expected_aaaa}"]


@BROWSER.command("page/command/screenshot", meta={"label": "Record screenshot artifact"})
def screenshot_command(domain: str = "", url: str = "", db: str = "", screenshot_dir: str = "", reason: str = "manual", meta: str = "") -> list[str]:
    return ["urirun-domain-monitor", "screenshot", "--domain", "{domain}", "--url", "{url}", "--db", "{db}", "--screenshot-dir", "{screenshot_dir}", "--reason", "{reason}", "--meta", "{meta}"]


@LOG.command("daily/command/write", meta={"label": "Write daily log"})
def log_write_command(stream: str = "daily", event: str = "", detail: str = "", db: str = "") -> list[str]:
    return ["urirun-domain-monitor", "log-write", "--stream", "{stream}", "--event", "{event}", "--detail", "{detail}", "--db", "{db}"]


@LOG.command("logs/query/recent", meta={"label": "Recent logs"})
def logs_recent_command(stream: str = "daily", limit: int = 20, db: str = "") -> list[str]:
    return ["urirun-domain-monitor", "logs-recent", "--stream", "{stream}", "--limit", "{limit}", "--db", "{db}"]


@FLOW.command("domain/command/check", meta={"label": "Run domain check flow"})
def domain_check_command(domain: str = "", url: str = "", expected_records: str = "", expected_a: str = "", expected_aaaa: str = "", db: str = "", project: str = "", timeout: float = 10.0, screenshot_when: str = "failure", screenshot_dir: str = "", create_repair_ticket: bool = True) -> list[str]:
    return ["urirun-domain-monitor", "domain-check", "--domain", "{domain}", "--url", "{url}", "--expected-records", "{expected_records}", "--expected-a", "{expected_a}", "--expected-aaaa", "{expected_aaaa}", "--db", "{db}", "--project", "{project}", "--timeout", "{timeout}", "--screenshot-when", "{screenshot_when}", "--screenshot-dir", "{screenshot_dir}", "--create-repair-ticket", "{create_repair_ticket}", "--execute", "true"]


@FLOW.command("daily/command/run", meta={"label": "Run daily domain checks"})
def daily_run_command(db: str = "", project: str = "", dataset: str = "domains", limit: int = 50, screenshot_when: str = "failure", screenshot_dir: str = "") -> list[str]:
    return ["urirun-domain-monitor", "daily-run", "--db", "{db}", "--project", "{project}", "--dataset", "{dataset}", "--limit", "{limit}", "--screenshot-when", "{screenshot_when}", "--screenshot-dir", "{screenshot_dir}", "--execute", "true"]


def urirun_bindings() -> dict[str, Any]:
    return urirun.connector_bindings(connector=CONNECTOR_ID)
