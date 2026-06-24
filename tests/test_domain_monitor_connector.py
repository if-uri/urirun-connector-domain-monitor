# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""domain-monitor connector: every route is a typed ``@handler(isolated=True)`` —
registry-portable (adapter ``local-function-subprocess``, ``python:{module,export}``,
no argv) and runnable from a COMPILED registry via the shared ``urirun.exec`` runner.
No real network/DNS/HTTP is touched: offline routes (dns/query/expected) compute
from the payload and log routes run against a tmp SQLite db."""
from __future__ import annotations

import json

import urirun
from urirun import v2
from urirun_connector_domain_monitor import (
    connector_manifest,
    dns_current,
    dns_expected,
    main,
    urirun_bindings,
)

MODULE = "urirun_connector_domain_monitor.core"

ROUTE_HTTP = "monitor://host/http/query/status"
ROUTE_DNS_CURRENT = "monitor://host/dns/query/current"
ROUTE_DNS_EXPECTED = "monitor://host/dns/query/expected"
ROUTE_SCREENSHOT = "browser://host/page/command/screenshot"
ROUTE_DOMAIN_CHECK = "flow://host/domain/command/check"
ROUTE_DAILY_RUN = "flow://host/daily/command/run"

# NB: no log:// routes — the log store is owned by the sqlite-context connector
# (dropping the duplicate avoids an exact-URI collision in a merged registry).
ALL_ROUTES = {
    ROUTE_HTTP, ROUTE_DNS_CURRENT, ROUTE_DNS_EXPECTED, ROUTE_SCREENSHOT,
    ROUTE_DOMAIN_CHECK, ROUTE_DAILY_RUN,
}

# route -> exported real-function name (the handler hydrated by python:{module,export})
ROUTE_EXPORTS = {
    ROUTE_HTTP: "http_status",
    ROUTE_DNS_CURRENT: "dns_current",
    ROUTE_DNS_EXPECTED: "dns_expected",
    ROUTE_SCREENSHOT: "screenshot",
    ROUTE_DOMAIN_CHECK: "domain_check",
    ROUTE_DAILY_RUN: "daily_run",
}

DM_RECORDS = [{"Name": "@", "Type": "A", "Address": "203.0.113.10"}]


# --- real impl functions called directly (offline / payload-only) ----------

def test_dns_expected_computes_from_payload():
    out = dns_expected(expected_a="203.0.113.10", expected_aaaa="2001:db8::1")
    assert out["ok"] is True
    assert out["connector"] == "domain-monitor"
    assert out["expectedRecords"]["A"] == ["203.0.113.10"]
    assert out["expectedRecords"]["AAAA"] == ["2001:db8::1"]


def test_dns_current_uses_payload_records_no_network():
    out = dns_current(domain="example.com", current_records=DM_RECORDS)
    assert out["ok"] is True
    assert out["source"] == "payload"
    assert out["records"][0]["Address"] == "203.0.113.10"


def test_dns_current_rejects_provider():
    out = dns_current(domain="example.com", provider="namecheap")
    assert out["ok"] is False
    assert "provider" in out["error"]


def test_no_log_routes_owned_by_sqlite_context():
    # domain-monitor must NOT expose log:// routes — they belong to sqlite-context.
    # Exposing duplicates was an exact-URI collision (urirun connectors doctor).
    assert not any(uri.startswith("log://") for uri in urirun_bindings()["bindings"])


# --- v2 authoring contract: isolated handlers (registry-portable) ----------

def test_bindings_are_isolated_handlers():
    b = urirun_bindings()["bindings"]
    assert set(b) == ALL_ROUTES
    for route, export in ROUTE_EXPORTS.items():
        # registry-portable handler: runs out-of-process via urirun.exec, no argv.
        assert b[route]["adapter"] == "local-function-subprocess"
        assert b[route]["python"]["module"] == MODULE
        assert b[route]["python"]["export"] == export
        assert "argv" not in b[route]
    # input schemas equal the handler signatures (route contracts unchanged).
    expected_props = b[ROUTE_DNS_EXPECTED]["inputSchema"]["properties"]
    assert set(expected_props) == {"expected_records", "expected_a", "expected_aaaa"}
    json.dumps(urirun_bindings())  # serializable: no live ref leaks


def test_compiles_and_routes_present():
    registry = urirun.compile_registry(urirun_bindings())
    uris = {r["uri"] for r in urirun.list_routes(registry)}
    assert ALL_ROUTES <= uris


def test_runtime_executes_offline_route_from_compiled_registry():
    # the deciding path: a serialized -> compiled registry still runs the route.
    # dns/query/expected is fully offline (it computes from the payload).
    registry = urirun.compile_registry(json.loads(json.dumps(urirun_bindings())))
    policy = urirun.policy(allow=["monitor://*"])

    env = v2.run(ROUTE_DNS_EXPECTED, registry,
                 payload={"expected_a": "203.0.113.10", "expected_aaaa": "2001:db8::1"},
                 mode="execute", policy=policy)
    assert env["ok"] is True
    data = urirun.result_data(env)
    assert data["ok"] is True
    assert data["connector"] == "domain-monitor"
    assert data["expectedRecords"]["A"] == ["203.0.113.10"]


def test_manifest_prose_plus_derived_routes():
    m = connector_manifest()
    assert m["id"] == "domain-monitor"
    assert set(m["routes"]) == ALL_ROUTES
    assert set(m["uriSchemes"]) == {"monitor", "browser", "flow"}  # no log:// (owned by sqlite-context)
    assert m["summary"]  # prose preserved
    assert m["install"]["mode"] == "urirun-extra"
    json.dumps(m)


# --- CLI -------------------------------------------------------------------

def test_cli_bindings_and_manifest(capsys):
    assert main(["bindings"]) == 0
    assert ALL_ROUTES <= set(json.loads(capsys.readouterr().out)["bindings"])
    assert main(["manifest"]) == 0
    assert json.loads(capsys.readouterr().out)["id"] == "domain-monitor"


def test_screenshot_tagged_as_frozen_artifact(monkeypatch):
    import urirun_connector_domain_monitor.core as core
    monkeypatch.setattr(core, "capture_screenshot_artifact",
                        lambda **kw: {"path": "/tmp/x.png", "uri": "artifact://host/screenshot/x"})
    r = core.screenshot(domain="example.com")
    assert r["ok"] is True
    # Shared urirun.tag contract: a screenshot is a frozen artifact.
    assert r["kind"] == "screenshot" and r["live"] is False
