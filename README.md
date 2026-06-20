# urirun-connector-domain-monitor

`domain-monitor` is an external urirun connector for HTTP checks, DNS reads,
Namecheap DNS planning, screenshot artifacts, logs and daily domain-check flows.

The package exposes URI bindings through decorators and executes them through a
small CLI:

```python
import urirun

DNS = urirun.connector("domain-monitor", scheme="dns")

@DNS.command("records/command/plan")
def dns_plan_command(domain: str = "", provider: str = "namecheap"):
    return ["urirun-domain-monitor", "dns-plan", "--domain", "{domain}", "--provider", "{provider}"]
```

## Install

```bash
pip install "git+https://github.com/if-uri/urirun-connector-domain-monitor.git@v0.1.0"
```

## Use

```bash
urirun-domain-monitor bindings > bindings.json
urirun validate bindings.json
urirun compile bindings.json --out registry.json

urirun run 'monitor://host/http/query/status' registry.json \
  --payload '{"domain":"example.com","url":"https://example.com/"}' \
  --execute \
  --allow 'monitor://host/*'
```

Namecheap routes can be tested safely with mock records:

```bash
urirun run 'dns://host/records/command/plan' registry.json \
  --payload '{"domain":"example.com","provider":"namecheap","current_records":"[{\"Name\":\"@\",\"Type\":\"A\",\"Address\":\"203.0.113.10\"}]","desired_records":"[{\"Name\":\"@\",\"Type\":\"A\",\"Address\":\"203.0.113.11\"}]"}' \
  --execute \
  --allow 'dns://host/*'
```

## Test

```bash
make test
make smoke
make docker-test
```

## Related projects

- Runtime: [if-uri/urirun](https://github.com/if-uri/urirun)
- Docs: [docs.ifuri.com/connectors.html](https://docs.ifuri.com/connectors.html) · [authoring a connector](https://docs.ifuri.com/connector-authoring.html)
- Hub page: [connect.ifuri.com/connectors/domain-monitor](https://connect.ifuri.com/connectors/domain-monitor)
- Connector hub: [connect.ifuri.com](https://connect.ifuri.com)
- Examples: [if-uri/examples](https://github.com/if-uri/examples)
- Work summary: [work-summary-2026-06-20](https://github.com/if-uri/docs/blob/main/work-summary-2026-06-20.md)

Repository notes: [TODO.md](TODO.md) · [CHANGELOG.md](CHANGELOG.md)
