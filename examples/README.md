# domain-monitor connector — examples

DNS + HTTP monitoring with screenshots.

## Install
```bash
urirun install urirun-connector-domain-monitor
```
`urirun install` resolves catalog ids via connect.ifuri.com; `--catalog <url>` points at a
local/on-prem registry; a full package name / git URL / path falls back to `pip install`.

## Run
```bash
# DNS + HTTP monitoring with screenshots (read)
urirun run 'monitor://host/dns/query/current' --payload '{"domain": "example.com", "current_records": "[{\"Name\":\"@\",\"Type\":\"A\",\"Address\":\"203.0.113.10\"}]"}' --execute --allow 'monitor://*'

# preview without running (dry-run): drop --execute
urirun run 'monitor://host/dns/query/current' --payload '{"domain": "example.com", "current_records": "[{\"Name\":\"@\",\"Type\":\"A\",\"Address\":\"203.0.113.10\"}]"}' --allow 'monitor://*'
```

## Inspect the runtime (no path — like error:// / log://)
```bash
urirun list | grep 'monitor://'                                   # this connector's routes
urirun run 'registry://local/routes/query/list' --payload '{"scheme":"monitor"}' --allow 'registry://*'
urirun run 'registry://local/bindings/query/show' --payload '{"uri":"monitor://host/dns/query/current"}' --allow 'registry://*'   # full typed contract
urirun errors                                                      # recent runtime errors (error://)
```

## Generate a client / API surface from the binding
```bash
urirun discover | urirun gen openapi - --out openapi.json   # OpenAPI 3 (one path per route)
urirun discover | urirun gen proto   - --out service.proto  # protobuf + gRPC (typed rpc per route)
urirun discover | urirun gen client  - --out client.py      # typed Python client
```
