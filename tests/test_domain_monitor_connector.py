# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

from __future__ import annotations

import contextlib
import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from urirun import v2
from urirun_connector_domain_monitor import (
    connector_manifest,
    dns_apply,
    dns_backup,
    dns_plan,
    domain_check,
    http_status,
    urirun_bindings,
)
from urirun_connector_domain_monitor.cli import main


CURRENT = [{"Name": "@", "Type": "A", "Address": "203.0.113.10", "TTL": 1800}]
DESIRED = [{"Name": "@", "Type": "A", "Address": "203.0.113.11", "TTL": 1800}]


class _Handler(BaseHTTPRequestHandler):
    status = 200

    def do_GET(self):  # noqa: N802 - stdlib callback name.
        self.send_response(self.status)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, _format, *args):
        return


@contextlib.contextmanager
def local_http(status: int = 200):
    class Handler(_Handler):
        pass

    Handler.status = status
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _registry():
    return v2.compile_registry(urirun_bindings())


def test_manifest_and_bindings_shape() -> None:
    manifest = connector_manifest()
    bindings = urirun_bindings()
    routes = v2.list_routes(_registry())

    assert manifest["id"] == "domain-monitor"
    assert "dns://host/records/command/plan" in manifest["routes"]
    assert "flow://host/domain/command/check" in manifest["routes"]
    assert bindings["version"] == "urirun.bindings.v2"
    assert "monitor://host/http/query/status" in bindings["bindings"]
    assert any(route["uri"] == "dns://host/records/command/apply" for route in routes)


def test_http_status_direct() -> None:
    with local_http(200) as url:
        result = http_status(domain="localhost", url=url)
    assert result["ok"] is True
    assert result["http"]["status"] == 200


def test_namecheap_plan_backup_apply_mock() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        current = json.dumps(CURRENT)
        desired = json.dumps(DESIRED)

        plan = dns_plan(domain="example.com", current_records=current, desired_records=desired)
        assert plan["ok"] is True
        assert plan["diff"]["changed"] is True

        backup = dns_backup(domain="example.com", current_records=current, db=str(Path(tmp) / "host.db"), backup_dir=str(Path(tmp) / "backups"))
        assert backup["ok"] is True
        assert Path(backup["backup"]["path"]).exists()

        applied = dns_apply(
            domain="example.com",
            current_records=current,
            plan=json.dumps(plan),
            backup_uri=backup["backup"]["uri"],
            confirm=True,
            mock_apply=True,
        )
        assert applied["ok"] is True
        assert applied["mock"] is True


def test_domain_check_writes_host_db() -> None:
    with tempfile.TemporaryDirectory() as tmp, local_http(200) as url:
        db = str(Path(tmp) / "host.db")
        result = domain_check(domain="localhost", url=url, db=db, execute=True, create_repair_ticket=False)
        assert result["ok"] is True
        from urirun import host_db

        assert host_db.recent_checks(db, subject="localhost")[0]["status"] == "ok"


def test_cli_and_urirun_run_connector_uri(capsys) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        bin_dir = Path(tmp) / "bin"
        bin_dir.mkdir()
        wrapper = bin_dir / "urirun-domain-monitor"
        wrapper.write_text(
            f"#!/usr/bin/env sh\nexec {sys.executable} -m urirun_connector_domain_monitor.cli \"$@\"\n",
            encoding="utf-8",
        )
        wrapper.chmod(0o755)
        previous_path = os.environ.get("PATH", "")
        os.environ["PATH"] = f"{bin_dir}{os.pathsep}{previous_path}"
        try:
            assert main(["bindings"]) == 0
            bindings = json.loads(capsys.readouterr().out)
            assert "dns://host/records/command/plan" in bindings["bindings"]

            result = v2.run(
                "dns://host/records/command/plan",
                _registry(),
                {
                    "domain": "example.com",
                    "provider": "namecheap",
                    "current_records": json.dumps(CURRENT),
                    "desired_records": json.dumps(DESIRED),
                },
                mode="execute",
                policy={"execute": {"allow": ["dns://host/*"]}},
            )
            assert result["ok"] is True, result
            stdout = json.loads(result["result"]["stdout"])
            assert stdout["diff"]["changed"] is True
        finally:
            os.environ["PATH"] = previous_path
