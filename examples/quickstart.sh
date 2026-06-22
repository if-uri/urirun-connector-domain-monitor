#!/usr/bin/env bash
# domain-monitor: install once, then run — auto-discovered, no registry path.
set -euo pipefail
urirun install urirun-connector-domain-monitor            # local dev: pip install -e .
urirun run 'monitor://host/dns/query/current' --payload '{"domain": "example.com", "current_records": "[{\"Name\":\"@\",\"Type\":\"A\",\"Address\":\"203.0.113.10\"}]"}' --execute --allow 'monitor://*'
