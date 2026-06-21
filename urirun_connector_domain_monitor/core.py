# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

from __future__ import annotations

import json
from typing import Any

import urirun
from urirun.host import domain_monitor as _dm, host_db as _host_db


CONNECTOR_ID = "domain-monitor"
MONITOR = urirun.connector(CONNECTOR_ID, scheme="monitor")
BROWSER = urirun.connector(CONNECTOR_ID, scheme="browser")
LOG = urirun.connector(CONNECTOR_ID, scheme="log")
FLOW = urirun.connector(CONNECTOR_ID, scheme="flow")



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


# Reuse the urirun host backend (single source of truth) instead of
# duplicating the SQLite store and HTTP/DNS/screenshot logic.
default_url = _dm.default_url
probe_http_status = _dm.http_status
resolve_dns_records = _dm.dns_records
expected_records_from_payload = _dm.expected_records
dns_mismatches = _dm.dns_mismatches
capture_screenshot_artifact = _dm.capture_screenshot_artifact
check_domain = _dm.check_domain
run_daily = _dm.run_daily
add_log = _host_db.add_log
recent_logs = _host_db.recent_logs
recent_checks = _host_db.recent_checks


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
