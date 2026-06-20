#!/usr/bin/env bash
# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

set -euo pipefail

mkdir -p .docker-smoke

echo "==> direct connector CLI"
python3 -m http.server 9876 --bind 127.0.0.1 --directory /tmp > .docker-smoke/http.log 2>&1 &
HTTP_PID="$!"
trap 'kill "$HTTP_PID" >/dev/null 2>&1 || true' EXIT
sleep 1

urirun-domain-monitor http-status --domain localhost --url http://127.0.0.1:9876/ > .docker-smoke/http.json
urirun-domain-monitor dns-current \
  --domain example.com \
  --current-records '[{"Name":"@","Type":"A","Address":"203.0.113.10"}]' > .docker-smoke/dns.json

echo "==> build bindings and registry"
python3 - <<'PY' > .docker-smoke/bindings.json
import json
from urirun_connector_domain_monitor import urirun_bindings
print(json.dumps(urirun_bindings(), indent=2))
PY

urirun validate .docker-smoke/bindings.json
urirun compile .docker-smoke/bindings.json --out .docker-smoke/registry.json

echo "==> execute connector URI through urirun"
urirun run 'monitor://host/dns/query/current' .docker-smoke/registry.json \
  --payload '{"domain":"example.com","current_records":"[{\"Name\":\"@\",\"Type\":\"A\",\"Address\":\"203.0.113.10\"}]"}' \
  --execute \
  --allow 'monitor://host/*' > .docker-smoke/urirun-result.json

echo "==> project registry to MCP tools and A2A card"
python3 -m urirun.v2_mcp tools .docker-smoke/registry.json > .docker-smoke/mcp-tools.json
python3 -m urirun.v2_mcp card .docker-smoke/registry.json \
  --name domain-monitor-docker \
  --url http://tester/ > .docker-smoke/a2a-card.json

python3 - <<'PY'
import json
from pathlib import Path

base = Path(".docker-smoke")
http = json.loads((base / "http.json").read_text())
dns = json.loads((base / "dns.json").read_text())
run = json.loads((base / "urirun-result.json").read_text())
run_payload = json.loads(run["result"]["stdout"])
tools = json.loads((base / "mcp-tools.json").read_text())
card = json.loads((base / "a2a-card.json").read_text())

assert http["ok"] is True, http
assert dns["records"][0]["Address"] == "203.0.113.10", dns
assert run["ok"] is True, run
assert run_payload["records"][0]["Address"] == "203.0.113.10", run_payload
assert any(tool["name"] == "monitor_host_dns_query_current" for tool in tools["tools"]), tools
assert any("monitor://host/dns/query/current" in skill.get("examples", []) for skill in card["skills"]), card
print(json.dumps({
    "ok": True,
    "mcpTools": len(tools["tools"]),
    "a2aSkills": len(card["skills"]),
}, indent=2))
PY
