# Changelog

## [Unreleased]

## [0.2.1] - 2026-06-20

### Changed
- Make the connector runtime self-contained for HTTP checks, DNS reads,
  screenshot artifacts, logs and daily checks.
- Stop importing `urirun.domain_monitor` and `urirun.host_db`; the connector
  now owns the minimal runtime/storage it needs.

## [0.2.0] - 2026-06-20

### Changed
- Move DNS read routes from `dns://host/records/query/*` to
  `monitor://host/dns/query/*`.
- Link README related projects to the `if-uri/urirun` runtime repository.
- Record that the connector is published and listed in the connector hub.

### Removed
- Remove Namecheap DNS plan, backup and apply bindings from this connector.
  Use `urirun-connector-namecheap-dns` for provider-specific `dns://` routes.

## [0.1.0] - 2026-06-20

### Added
- Add initial domain monitor connector with decorated HTTP, DNS, Namecheap,
  screenshot, log and flow URI bindings.
