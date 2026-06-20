from __future__ import annotations

import json
from importlib import resources
from typing import Any

import urirun


CONNECTOR_ID = "domain-monitor"
MONITOR = urirun.connector(CONNECTOR_ID, scheme="monitor")
DNS = urirun.connector(CONNECTOR_ID, scheme="dns")
BROWSER = urirun.connector(CONNECTOR_ID, scheme="browser")
LOG = urirun.connector(CONNECTOR_ID, scheme="log")
FLOW = urirun.connector(CONNECTOR_ID, scheme="flow")


def _json_resource(name: str) -> dict[str, Any]:
    text = resources.files(__package__).joinpath(name).read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"{name} must contain a JSON object")
    return data


def connector_manifest() -> dict[str, Any]:
    return _json_resource("connector.manifest.json")


def _domain_monitor():
    from urirun import domain_monitor

    return domain_monitor


def _namecheap_dns():
    from urirun import namecheap_dns

    return namecheap_dns


def _host_db():
    from urirun import host_db

    return host_db


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


def _payload_records(
    *,
    current_records: str = "",
    desired_records: str = "",
    ensure_records: str = "",
    remove_records: str = "",
    plan: str = "",
    backup_uri: str = "",
    confirm: bool | str = False,
    mock_apply: bool | str = False,
    allow_current_drift: bool | str = False,
    backup_dir: str = "",
    profile: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if current_records:
        payload["current_records"] = _json_value(current_records, [])
    if desired_records:
        payload["desired_records"] = _json_value(desired_records, [])
    if ensure_records:
        payload["ensure_records"] = _json_value(ensure_records, [])
    if remove_records:
        payload["remove_records"] = _json_value(remove_records, [])
    if plan:
        payload["plan"] = _json_value(plan, {})
    if backup_uri:
        payload["backup_uri"] = backup_uri
    if backup_dir:
        payload["backup_dir"] = backup_dir
    if profile:
        payload["profile"] = profile
    payload["confirm"] = _bool(confirm)
    payload["mock_apply"] = _bool(mock_apply)
    payload["allow_current_drift"] = _bool(allow_current_drift)
    return payload


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
    monitor = _domain_monitor()
    target = domain or "localhost"
    check_url = url or monitor.default_url(target)
    result = monitor.http_status(check_url, timeout=float(timeout), expected_status=_int_or_none(expected_status))
    return {"ok": bool(result.get("ok")), "connector": CONNECTOR_ID, "type": "domain-monitor", "domain": target, "http": result}


def dns_current(domain: str = "", provider: str = "", record_types: str = "", current_records: str = "", profile: str = "") -> dict[str, Any]:
    target = domain or "localhost"
    payload = _payload_records(current_records=current_records, profile=profile)
    if provider.lower() == "namecheap":
        records = _namecheap_dns().current_records(target, payload)
        return {"ok": True, "connector": CONNECTOR_ID, "type": "namecheap-dns", "domain": target, "records": records}
    result = _domain_monitor().dns_records(target, _split_csv(record_types) or None)
    return {"ok": bool(result.get("ok")), "connector": CONNECTOR_ID, "type": "domain-monitor", **result}


def dns_expected(expected_records: str = "", expected_a: str = "", expected_aaaa: str = "") -> dict[str, Any]:
    payload = _expected_payload(expected_records=expected_records, expected_a=expected_a, expected_aaaa=expected_aaaa)
    return {"ok": True, "connector": CONNECTOR_ID, "type": "domain-monitor", "expectedRecords": _domain_monitor().expected_records(payload)}


def dns_plan(
    domain: str = "",
    provider: str = "namecheap",
    current_records: str = "",
    desired_records: str = "",
    ensure_records: str = "",
    remove_records: str = "",
    profile: str = "",
) -> dict[str, Any]:
    target = domain or "localhost"
    payload = _payload_records(
        current_records=current_records,
        desired_records=desired_records,
        ensure_records=ensure_records,
        remove_records=remove_records,
        profile=profile,
    )
    if provider.lower() != "namecheap":
        current = dns_current(domain=target)
        return {"ok": current.get("ok", False), "connector": CONNECTOR_ID, "type": "domain-monitor", "action": "plan", "domain": target, "current": current}
    return {"connector": CONNECTOR_ID, "action": "plan", **_namecheap_dns().plan(target, payload)}


def dns_backup(domain: str = "", provider: str = "namecheap", current_records: str = "", backup_dir: str = "", db: str = "", profile: str = "") -> dict[str, Any]:
    if provider.lower() != "namecheap":
        raise ValueError("dns backup currently supports provider=namecheap")
    target = domain or "localhost"
    payload = _payload_records(current_records=current_records, backup_dir=backup_dir, profile=profile)
    records = _namecheap_dns().current_records(target, payload)
    artifact = _namecheap_dns().backup(target, records, db=db or None, out_dir=backup_dir or None)
    return {"ok": True, "connector": CONNECTOR_ID, "type": "namecheap-dns", "action": "backup", "domain": target, "backup": artifact}


def dns_apply(
    domain: str = "",
    provider: str = "namecheap",
    current_records: str = "",
    desired_records: str = "",
    plan: str = "",
    backup_uri: str = "",
    confirm: bool = False,
    mock_apply: bool = True,
    allow_current_drift: bool = False,
    profile: str = "",
) -> dict[str, Any]:
    if provider.lower() != "namecheap":
        raise ValueError("dns apply currently supports provider=namecheap")
    payload = _payload_records(
        current_records=current_records,
        desired_records=desired_records,
        plan=plan,
        backup_uri=backup_uri,
        confirm=confirm,
        mock_apply=mock_apply,
        allow_current_drift=allow_current_drift,
        profile=profile,
    )
    return {"connector": CONNECTOR_ID, "action": "apply", **_namecheap_dns().apply(domain or "localhost", payload)}


def screenshot(domain: str = "", url: str = "", db: str = "", screenshot_dir: str = "", reason: str = "manual", meta: str = "") -> dict[str, Any]:
    monitor = _domain_monitor()
    target = domain or "localhost"
    artifact = monitor.capture_screenshot_artifact(
        db=db or None,
        domain=target,
        url=url or monitor.default_url(target),
        out_dir=screenshot_dir or None,
        reason=reason,
        meta=_json_value(meta, {}),
    )
    return {"ok": True, "connector": CONNECTOR_ID, "type": "domain-monitor", "artifact": artifact}


def log_write(stream: str = "daily", event: str = "", detail: str = "", db: str = "") -> dict[str, Any]:
    if not event:
        raise ValueError("event is required")
    log = _host_db().add_log(db or None, stream, event, _json_value(detail, {}))
    return {"ok": True, "connector": CONNECTOR_ID, "type": "domain-monitor", "log": log}


def logs_recent(stream: str = "daily", limit: int = 20, db: str = "") -> dict[str, Any]:
    logs = _host_db().recent_logs(db or None, stream=stream, limit=int(limit))
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
    expected = _domain_monitor().expected_records(payload)
    result = _domain_monitor().check_domain(
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
    result = _domain_monitor().run_daily(
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
        "dns-plan": dns_plan,
        "dns-backup": dns_backup,
        "dns-apply": dns_apply,
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


@DNS.command("records/query/current", meta={"label": "Current DNS records"})
def dns_current_command(domain: str = "", provider: str = "", record_types: str = "", current_records: str = "", profile: str = "") -> list[str]:
    return ["urirun-domain-monitor", "dns-current", "--domain", "{domain}", "--provider", "{provider}", "--record-types", "{record_types}", "--current-records", "{current_records}", "--profile", "{profile}"]


@DNS.command("records/query/expected", meta={"label": "Expected DNS records"})
def dns_expected_command(expected_records: str = "", expected_a: str = "", expected_aaaa: str = "") -> list[str]:
    return ["urirun-domain-monitor", "dns-expected", "--expected-records", "{expected_records}", "--expected-a", "{expected_a}", "--expected-aaaa", "{expected_aaaa}"]


@DNS.command("records/command/plan", meta={"label": "Plan DNS changes"})
def dns_plan_command(domain: str = "", provider: str = "namecheap", current_records: str = "", desired_records: str = "", ensure_records: str = "", remove_records: str = "", profile: str = "") -> list[str]:
    return ["urirun-domain-monitor", "dns-plan", "--domain", "{domain}", "--provider", "{provider}", "--current-records", "{current_records}", "--desired-records", "{desired_records}", "--ensure-records", "{ensure_records}", "--remove-records", "{remove_records}", "--profile", "{profile}"]


@DNS.command("records/command/backup", meta={"label": "Backup DNS records"})
def dns_backup_command(domain: str = "", provider: str = "namecheap", current_records: str = "", backup_dir: str = "", db: str = "", profile: str = "") -> list[str]:
    return ["urirun-domain-monitor", "dns-backup", "--domain", "{domain}", "--provider", "{provider}", "--current-records", "{current_records}", "--backup-dir", "{backup_dir}", "--db", "{db}", "--profile", "{profile}"]


@DNS.command("records/command/apply", meta={"label": "Apply DNS changes"})
def dns_apply_command(domain: str = "", provider: str = "namecheap", current_records: str = "", desired_records: str = "", plan: str = "", backup_uri: str = "", confirm: bool = False, mock_apply: bool = True, allow_current_drift: bool = False, profile: str = "") -> list[str]:
    return ["urirun-domain-monitor", "dns-apply", "--domain", "{domain}", "--provider", "{provider}", "--current-records", "{current_records}", "--desired-records", "{desired_records}", "--plan", "{plan}", "--backup-uri", "{backup_uri}", "--confirm", "{confirm}", "--mock-apply", "{mock_apply}", "--allow-current-drift", "{allow_current_drift}", "--profile", "{profile}"]


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
