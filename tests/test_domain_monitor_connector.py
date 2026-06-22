# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""domain-monitor connector: @handler routes are route-equivalent to the host
backend and run in-process — including from a compiled FILE registry (no _exec.py)."""
from __future__ import annotations

import json

import urirun
from urirun.runtime import _runtime
from urirun_connector_domain_monitor import core

DM_RECORDS = [{"Name": "@", "Type": "A", "Address": "203.0.113.10"}]


def test_eight_local_function_routes():
    b = core.urirun_bindings()["bindings"]
    assert len(b) == 8
    assert {e["adapter"] for e in b.values()} == {"local-function"}
    for uri in ("monitor://host/http/query/status", "monitor://host/dns/query/current",
                "flow://host/domain/command/check", "log://host/logs/query/recent"):
        assert uri in b


def test_handler_runs_in_process():
    out = core.http_status(domain="example.com", url="https://example.com")
    assert "ok" in out and out["connector"] == "domain-monitor" and "http" in out


def test_runs_from_compiled_file_registry(tmp_path):
    # the deciding path: compile to a registry doc, run a local-function route through
    # urirun.run — the handler is hydrated from python:{module,export}, no argv shim.
    doc = core.urirun_bindings()
    reg_path = tmp_path / "reg.json"
    reg_path.write_text(json.dumps(urirun.compile_registry(doc)))
    registry = _runtime.load_registry_arg(str(reg_path))
    policy = _runtime.build_policy(None, ["monitor://*"], None)
    result = urirun.run("monitor://host/dns/query/current", registry,
                        {"domain": "example.com", "current_records": DM_RECORDS},
                        mode="execute", policy=policy)
    assert result["ok"] is True
    value = result["result"]["value"]
    # current_records arrived as a real list (typed by the schema), used directly —
    # no _bool/_json_value string-coercion, because the runtime types from the signature.
    assert value["records"][0]["Address"] == "203.0.113.10"
    assert value["source"] == "payload"


def test_manifest_machine_fields_derive_from_handlers():
    # Connector.manifest fills routes/uriSchemes/adapterKinds from the @handlers,
    # so the prose manifest can never drift from the code.
    manifest = core.connector_manifest()
    assert manifest["id"] == "domain-monitor"
    assert len(manifest.get("routes", [])) == 8
    assert set(manifest.get("uriSchemes", [])) >= {"monitor", "browser", "log", "flow"}
