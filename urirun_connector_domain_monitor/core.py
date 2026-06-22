# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# domain-monitor connector — v2 authoring. Each route is declared ONCE as a
# ``@handler`` (a local-function binding): the typed signature is the input schema,
# the body is the work. No argv ``*_command`` twin, no ``run_action`` dispatch table,
# no ``_exec.py`` argv shim, and no hand-written ``main``/``manifest``/``bindings`` —
# the runtime hydrates the function from the serialized ``python: {module, export}``
# descriptor (pip already makes the module importable), so a route runs in-process
# from a file registry, ``urirun run``, or a served node alike.

from __future__ import annotations

from typing import Any

import urirun
from urirun.host import domain_monitor as _dm, host_db as _host_db

CONNECTOR_ID = "domain-monitor"
MONITOR = urirun.connector(CONNECTOR_ID, scheme="monitor")
BROWSER = urirun.connector(CONNECTOR_ID, scheme="browser")
LOG = urirun.connector(CONNECTOR_ID, scheme="log")
FLOW = urirun.connector(CONNECTOR_ID, scheme="flow")

# Reuse the urirun host backend (single source of truth).
default_url = _dm.default_url
probe_http_status = _dm.http_status
resolve_dns_records = _dm.dns_records
expected_records_from_payload = _dm.expected_records
capture_screenshot_artifact = _dm.capture_screenshot_artifact
check_domain = _dm.check_domain
run_daily = _dm.run_daily
add_log = _host_db.add_log
recent_logs = _host_db.recent_logs


def _expected_payload(expected_records, expected_a: str, expected_aaaa: str) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if expected_records:
        payload["expected_records"] = expected_records
    if expected_a:
        payload["expected_a"] = expected_a
    if expected_aaaa:
        payload["expected_aaaa"] = expected_aaaa
    return payload


def _split_csv(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    return [item.strip() for item in str(value).split(",") if item.strip()]


@MONITOR.handler("http/query/status", meta={"label": "HTTP status check"})
def http_status(domain: str = "", url: str = "", timeout: float = 10.0, expected_status: int = 0) -> dict[str, Any]:
    target = domain or "localhost"
    result = probe_http_status(url or default_url(target), timeout=timeout, expected_status=expected_status or None)
    return {"ok": bool(result.get("ok")), "connector": CONNECTOR_ID, "type": "domain-monitor", "domain": target, "http": result}


@MONITOR.handler("dns/query/current", meta={"label": "Current DNS records"})
def dns_current(domain: str = "", provider: str = "", record_types: list | None = None,
                current_records: list | None = None, profile: str = "") -> dict[str, Any]:
    target = domain or "localhost"
    if current_records:
        return {"ok": True, "connector": CONNECTOR_ID, "type": "domain-monitor", "domain": target,
                "records": current_records, "source": "payload", "profile": profile}
    if provider:
        return {"ok": False, "connector": CONNECTOR_ID, "type": "domain-monitor", "domain": target,
                "error": f"provider={provider} is handled by a provider-specific connector"}
    result = resolve_dns_records(target, _split_csv(record_types) or None)
    return {"ok": bool(result.get("ok")), "connector": CONNECTOR_ID, "type": "domain-monitor", **result}


@MONITOR.handler("dns/query/expected", meta={"label": "Expected DNS records"})
def dns_expected(expected_records: dict | None = None, expected_a: str = "", expected_aaaa: str = "") -> dict[str, Any]:
    payload = _expected_payload(expected_records or {}, expected_a, expected_aaaa)
    return {"ok": True, "connector": CONNECTOR_ID, "type": "domain-monitor",
            "expectedRecords": expected_records_from_payload(payload)}


@BROWSER.handler("page/command/screenshot", meta={"label": "Record screenshot artifact"})
def screenshot(domain: str = "", url: str = "", db: str = "", screenshot_dir: str = "",
               reason: str = "manual", meta: dict | None = None) -> dict[str, Any]:
    target = domain or "localhost"
    artifact = capture_screenshot_artifact(db=db or None, domain=target, url=url or default_url(target),
                                           out_dir=screenshot_dir or None, reason=reason, meta=meta or {})
    return {"ok": True, "connector": CONNECTOR_ID, "type": "domain-monitor", "artifact": artifact}


@LOG.handler("daily/command/write", meta={"label": "Write daily log"})
def log_write(stream: str = "daily", event: str = "", detail: dict | None = None, db: str = "") -> dict[str, Any]:
    if not event:
        return urirun.fail("event is required", connector=CONNECTOR_ID)
    return {"ok": True, "connector": CONNECTOR_ID, "type": "domain-monitor",
            "log": add_log(db or None, stream, event, detail or {})}


@LOG.handler("logs/query/recent", meta={"label": "Recent logs"})
def logs_recent(stream: str = "daily", limit: int = 20, db: str = "") -> dict[str, Any]:
    return {"ok": True, "connector": CONNECTOR_ID, "type": "domain-monitor",
            "logs": recent_logs(db or None, stream=stream, limit=limit)}


@FLOW.handler("domain/command/check", meta={"label": "Run domain check flow"})
def domain_check(domain: str = "", url: str = "", expected_records: dict | None = None, expected_a: str = "",
                 expected_aaaa: str = "", db: str = "", project: str = "", timeout: float = 10.0,
                 screenshot_when: str = "failure", screenshot_dir: str = "",
                 create_repair_ticket: bool = True, execute: bool = True) -> dict[str, Any]:
    expected = expected_records_from_payload(_expected_payload(expected_records or {}, expected_a, expected_aaaa))
    result = check_domain(domain=domain or "localhost", url=url or None, expected=expected, db=db or None,
                          project=project or None, execute=execute, timeout=timeout, screenshot_when=screenshot_when,
                          screenshot_dir=screenshot_dir or None, create_repair_ticket=create_repair_ticket)
    return {"connector": CONNECTOR_ID, "type": "domain-monitor", "flow": "domain-check", **result}


@FLOW.handler("daily/command/run", meta={"label": "Run daily domain checks"})
def daily_run(db: str = "", project: str = "", dataset: str = "domains", limit: int = 50,
              screenshot_when: str = "failure", screenshot_dir: str = "", execute: bool = True) -> dict[str, Any]:
    result = run_daily(db=db or None, project=project or None, execute=execute, dataset=dataset, limit=limit,
                       screenshot_when=screenshot_when, screenshot_dir=screenshot_dir or None)
    return {"connector": CONNECTOR_ID, "type": "domain-monitor", "flow": "daily-domain-run", **result}


# authoring surface — all derived from the declared @handlers, zero boilerplate.
urirun_bindings = MONITOR.bindings


def connector_manifest() -> dict[str, Any]:
    """Full manifest: prose from connector.manifest.json + machine fields derived
    from the @handlers (routes/uriSchemes/adapterKinds), so they can't drift."""
    return MONITOR.manifest(urirun.load_manifest(__package__))


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: subcommands + dispatch + manifest, all derived from the handlers."""
    return MONITOR.cli(argv, manifest_prose=urirun.load_manifest(__package__))
