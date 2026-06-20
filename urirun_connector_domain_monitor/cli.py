# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

from __future__ import annotations

import argparse
import sys

import urirun

from .core import connector_manifest, run_action, urirun_bindings




def _bool_text(value: str) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _add_domain(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--domain", default="")


def _add_db(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--db", default="")


def _add_expected(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--expected-records", default="")
    parser.add_argument("--expected-a", default="")
    parser.add_argument("--expected-aaaa", default="")


def _add_screenshot(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--screenshot-when", default="failure")
    parser.add_argument("--screenshot-dir", default="")


def register(sub) -> None:

    http = sub.add_parser("http-status", help="Check HTTP status")
    _add_domain(http)
    http.add_argument("--url", default="")
    http.add_argument("--timeout", type=float, default=10.0)
    http.add_argument("--expected-status", type=int, default=0)

    dns_current = sub.add_parser("dns-current", help="Read current DNS records")
    _add_domain(dns_current)
    dns_current.add_argument("--provider", default="")
    dns_current.add_argument("--record-types", default="")
    dns_current.add_argument("--current-records", default="")
    dns_current.add_argument("--profile", default="")

    dns_expected = sub.add_parser("dns-expected", help="Render expected DNS records")
    _add_expected(dns_expected)

    shot = sub.add_parser("screenshot", help="Record screenshot artifact metadata")
    _add_domain(shot)
    shot.add_argument("--url", default="")
    shot.add_argument("--reason", default="manual")
    shot.add_argument("--meta", default="")
    shot.add_argument("--screenshot-dir", default="")
    _add_db(shot)

    log_write = sub.add_parser("log-write", help="Write a log record")
    log_write.add_argument("--stream", default="daily")
    log_write.add_argument("--event", required=True)
    log_write.add_argument("--detail", default="")
    _add_db(log_write)

    logs = sub.add_parser("logs-recent", help="Read recent log records")
    logs.add_argument("--stream", default="daily")
    logs.add_argument("--limit", type=int, default=20)
    _add_db(logs)

    domain_check = sub.add_parser("domain-check", help="Run HTTP/DNS domain check")
    _add_domain(domain_check)
    domain_check.add_argument("--url", default="")
    _add_expected(domain_check)
    _add_db(domain_check)
    domain_check.add_argument("--project", default="")
    domain_check.add_argument("--timeout", type=float, default=10.0)
    _add_screenshot(domain_check)
    domain_check.add_argument("--create-repair-ticket", type=_bool_text, default=True)
    domain_check.add_argument("--execute", type=_bool_text, default=True)

    daily = sub.add_parser("daily-run", help="Run checks from host dataset")
    _add_db(daily)
    daily.add_argument("--project", default="")
    daily.add_argument("--dataset", default="domains")
    daily.add_argument("--limit", type=int, default=50)
    _add_screenshot(daily)
    daily.add_argument("--execute", type=_bool_text, default=True)


def dispatch(args) -> int:
    data = vars(args)
    command = data.pop("command")
    try:
        result = run_action(command, **data)
    except Exception as exc:  # noqa: BLE001 - connector CLI reports JSON errors.
        urirun.connector_emit({"ok": False, "connector": "domain-monitor", "action": command, "error": str(exc)})
        return 2
    urirun.connector_emit(result)
    return 0 if result.get("ok") else 2


def main(argv: list[str] | None = None) -> int:
    return urirun.connector_cli(
        "urirun-domain-monitor",
        manifest=connector_manifest,
        bindings=urirun_bindings,
        register=register,
        dispatch=dispatch,
        argv=argv,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
