# urirun-connector-domain-monitor

`domain-monitor` is an external urirun connector for HTTP checks, DNS reads,
screenshot artifacts, logs and daily domain-check flows.

Each route is declared once as a typed `@handler(isolated=True)`: the function
signature is the input schema and the body is the implementation — no argv
`*_command` twin, no `_exec.py` shim, no `run_action` dispatcher. `isolated=True`
runs each route out-of-process through the shared `python -m urirun.exec` runner,
so the bindings stay **registry-portable** (they execute from a compiled/served
registry with only the package importable). The four connector objects
(`MONITOR`/`BROWSER`/`LOG`/`FLOW`) share the one `domain-monitor` connector id, so
one `urirun_bindings()` returns every route:

```python
import urirun

MONITOR = urirun.connector("domain-monitor", scheme="monitor")

@MONITOR.handler("http/query/status", isolated=True, meta={"label": "HTTP status check"})
def http_status(domain: str = "", url: str = "", timeout: float = 10.0, expected_status: int = 0):
    ...  # the body is the implementation
```

## Install

```bash
pip install "git+https://github.com/if-uri/urirun-connector-domain-monitor.git@v0.2.1"
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

DNS reads can be tested safely with mock records:

```bash
urirun run 'monitor://host/dns/query/current' registry.json \
  --payload '{"domain":"example.com","current_records":"[{\"Name\":\"@\",\"Type\":\"A\",\"Address\":\"203.0.113.10\"}]"}' \
  --execute \
  --allow 'monitor://host/*'
```

After installation, `urirun` can discover this connector automatically through
the `urirun.bindings` entry-point group:

```bash
urirun discover --out connectors.bindings.json --registry-out connectors.registry.json
urirun list --entry-points
```

Provider-specific DNS mutations are intentionally outside this connector.
Use [`urirun-connector-namecheap-dns`](https://github.com/if-uri/urirun-connector-namecheap-dns)
for `dns://host/records/command/plan`, backup and apply routes.

The connector owns its HTTP/DNS runtime and lightweight SQLite log/check/artifact
store. It does not import `urirun.domain_monitor`, `urirun.host_db` or
`urirun.namecheap_dns` from the core runtime.

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

## License

Released under the terms in [LICENSE](LICENSE).
