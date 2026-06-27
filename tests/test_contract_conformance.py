# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
"""Conformance gate for the domain-monitor connector's route contracts.

The connector does network I/O (HTTP/DNS) and browser capture, so the gate is STATIC for those
routes (conform + faithful examples). The two network-free routes — dns/query/expected (pure
transform) and dns/query/current with ``current_records`` (payload passthrough) — additionally get
LIVE-output conformance: the real handler runs and its envelope is checked against the contract.
"""
from __future__ import annotations

import urirun_connector_domain_monitor.core as core
from urirun_connector_domain_monitor.contracts import CONTRACTS
from urirun_connectors_toolkit.contract_gate import conform, envelope_violation
from urirun_connectors_toolkit.contract_lint import lint_handler_signatures


def test_contracts_conform():
    """Static oracle: effect↔verb, golden examples satisfy in/out, error taxonomy."""
    conform(CONTRACTS)


def test_signatures_bound_to_contract():
    """Every contract.inp field must exist in the live handler signature with a compatible type."""
    problems = lint_handler_signatures(CONTRACTS, core.urirun_bindings())
    assert not problems, "contract<->signature drift:\n" + "\n".join(problems)


def test_every_route_has_a_contract():
    """Full coverage + dangling guard: every live route is contracted and no contract points at a
    route that does not exist."""
    live = set(core.urirun_bindings()["bindings"])
    contracted = set(CONTRACTS)
    assert not (contracted - live), f"contracts point at missing routes: {sorted(contracted - live)}"
    assert not (live - contracted), f"routes without a contract: {sorted(live - contracted)}"


def test_network_free_routes_conform_live():
    """Run the two network-free handlers and assert real output conforms (no network/browser)."""
    cases = [
        ("monitor://host/dns/query/expected",
         lambda: core.dns_expected(expected_a="1.2.3.4", expected_aaaa="::1")),
        ("monitor://host/dns/query/current",
         lambda: core.dns_current(domain="ifuri.com", current_records=[{"type": "A", "value": "1.2.3.4"}])),
    ]
    for uri, run in cases:
        env = run()
        bad = envelope_violation(CONTRACTS[uri], env)
        assert bad is None, f"{uri}: live output violates contract: {bad}\nenvelope={env}"
