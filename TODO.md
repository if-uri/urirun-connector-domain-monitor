# TODO

- [x] Publish `if-uri/urirun-connector-domain-monitor`.
- [x] Move Namecheap DNS URI bindings to `urirun-connector-namecheap-dns`.
- [x] Move remaining domain monitor runtime code fully out of urirun core.
- [ ] Add this connector to IFURI-016 full host-node Docker matrix with
      `monitor://` checks, logs and artifacts.
- [ ] Add compatibility examples that compose domain checks with provider-specific DNS connectors.
- [ ] Add browser screenshot integration with a real browser connector.
- [ ] Publish route schemas, expected payloads and policy notes on the connector
      detail page.
- [ ] Remove `urirun.domain_monitor` and `urirun.host_db` compatibility modules
      from core after downstream examples stop importing them directly.
