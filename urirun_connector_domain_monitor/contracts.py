# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
"""Route contracts for the domain-monitor connector (LLM-editable declaration).

Multi-scheme (monitor/browser/flow share one connector id) → contract keys are FULL URIs and
``attach_contracts(None, CONTRACTS)`` joins them. This connector does network I/O (HTTP/DNS) and
browser capture, so the gate is STATIC (conform + faithful examples) for the network/browser routes;
the two network-free routes (dns/query/expected = pure transform, dns/query/current with
``current_records`` = payload passthrough) additionally get LIVE-output conformance in the test.

Examples for network/browser routes are reconstructed from host_service return shapes (http_status /
dns_records / check_domain / run_daily / register_artifact); the network-free examples are captured
from real execution. conform() checks STRUCTURE, not exact values.
"""
from __future__ import annotations

from urirun_connectors_toolkit.contract_gate import Contract

CONTRACTS: dict[str, Contract] = {

    "monitor://host/http/query/status": Contract(
        version="v1", effect="query",
        inp={"domain": "?str", "url": "?str", "timeout": "?num", "expected_status": "?int"},
        out={"ok": "bool", "connector": "const:domain-monitor", "type": "const:domain-monitor",
             "domain": "str", "http": "obj"},
        examples=(
            {"payload": {"domain": "ifuri.com"},
             "result": {"ok": True, "connector": "domain-monitor", "type": "domain-monitor",
                        "domain": "ifuri.com",
                        "http": {"ok": True, "url": "https://ifuri.com", "status": 200,
                                 "elapsedMs": 120, "headers": {}}}},
        )),

    "monitor://host/dns/query/current": Contract(
        version="v1", effect="query",
        inp={"domain": "?str", "provider": "?str", "record_types": "?list",
             "current_records": "?list", "profile": "?str"},
        out={"oneOf": [
            # payload passthrough (records is the supplied list)
            {"ok": "const:true", "type": "const:domain-monitor", "records": "list", "source": "const:payload"},
            # system resolver (records is the {A,AAAA} object)
            {"ok": "bool", "type": "const:domain-monitor", "domain": "str", "records": "obj", "provider": "str"},
        ]},
        examples=(
            {"payload": {"domain": "ifuri.com", "current_records": [{"type": "A", "value": "1.2.3.4"}]},
             "result": {"ok": True, "connector": "domain-monitor", "type": "domain-monitor",
                        "domain": "ifuri.com", "records": [{"type": "A", "value": "1.2.3.4"}],
                        "source": "payload", "profile": ""}},
            {"payload": {"domain": "ifuri.com"},
             "result": {"ok": True, "connector": "domain-monitor", "type": "domain-monitor",
                        "domain": "ifuri.com", "records": {"A": ["1.2.3.4"], "AAAA": []},
                        "provider": "system-resolver"}},
        )),

    "monitor://host/dns/query/expected": Contract(
        version="v1", effect="query",
        inp={"expected_records": "?obj", "expected_a": "?str", "expected_aaaa": "?str"},
        out={"ok": "const:true", "type": "const:domain-monitor", "expectedRecords": "obj"},
        examples=(
            {"payload": {"expected_a": "1.2.3.4", "expected_aaaa": "::1"},
             "result": {"ok": True, "connector": "domain-monitor", "type": "domain-monitor",
                        "expectedRecords": {"A": ["1.2.3.4"], "AAAA": ["::1"]}}},
        )),

    "browser://host/page/command/screenshot": Contract(
        version="v1", effect="command",
        inp={"domain": "?str", "url": "?str", "db": "?str", "screenshot_dir": "?str",
             "reason": "?str", "meta": "?obj"},
        out={"ok": "const:true", "type": "const:domain-monitor", "artifact": "obj", "live": "bool"},
        examples=(
            {"payload": {"domain": "ifuri.com", "reason": "manual"},
             "result": {"ok": True, "connector": "domain-monitor", "type": "domain-monitor",
                        "artifact": {"id": "art_x", "kind": "screenshot", "uri": "browser://ifuri.com",
                                     "path": "/shots/ifuri.png", "created_at": "2026-06-27T10:36:30Z",
                                     "meta": {}}, "live": False}},
        )),

    "flow://host/domain/command/check": Contract(
        version="v1", effect="command",
        inp={"domain": "?str", "url": "?str", "expected_records": "?obj", "db": "?str",
             "project": "?str", "timeout": "?num", "screenshot_when": "?str", "execute": "?bool"},
        out={"connector": "const:domain-monitor", "type": "const:domain-monitor",
             "flow": "const:domain-check", "ok": "bool"},
        examples=(
            {"payload": {"domain": "ifuri.com", "expected_a": "1.2.3.4"},
             "result": {"connector": "domain-monitor", "type": "domain-monitor", "flow": "domain-check",
                        "ok": True, "domain": "ifuri.com",
                        "http": {"ok": True, "status": 200}, "dns": {"ok": True, "records": {"A": ["1.2.3.4"]}},
                        "mismatches": [], "artifacts": [], "tickets": []}},
        )),

    "flow://host/daily/command/run": Contract(
        version="v1", effect="command",
        inp={"db": "?str", "project": "?str", "dataset": "?str", "limit": "?int",
             "screenshot_when": "?str", "execute": "?bool"},
        out={"connector": "const:domain-monitor", "type": "const:domain-monitor",
             "flow": "const:daily-domain-run", "ok": "bool", "count": "int", "results": "list",
             "executed": "bool"},
        examples=(
            {"payload": {"dataset": "domains", "limit": 50},
             "result": {"connector": "domain-monitor", "type": "domain-monitor", "flow": "daily-domain-run",
                        "ok": True, "count": 1,
                        "results": [{"domain": "ifuri.com", "ok": True}], "executed": True}},
        )),
}
