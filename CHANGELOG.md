# Changelog

All notable changes to `homedata-mcp` will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-05-11

### Added
- New `homedata` CLI command, installed alongside `homedata-mcp`. Same auth
  (`HOMEDATA_API_KEY` env var), same data, different surface — designed for
  shell pipelines, scripting, and quick lookups.
  ```bash
  homedata property 100021421083
  homedata epc 100021421083 --field current_energy_efficiency
  homedata search "10 downing street" --postcode SW1A2AA
  homedata batch 100021421083 100022121211
  ```
  Supports `--compact` for single-line JSON and `--field <path>` to extract
  a single value for piping into other tools.

## [0.1.2] - 2026-05-11

### Changed
- Package now lives in its own public repository at
  https://github.com/wehomemove/homedata-mcp (split out from the internal
  `wehomemove/loki` monorepo so users can browse the source freely).
- Project metadata URLs (`Source`, `Issues`, `Changelog`) updated to point at
  the new repository.
- Release workflow now triggers on `v*` tags (e.g. `v0.1.2`) instead of the
  previous `homedata-mcp-v*` prefix.

No behavioural changes to any tool.

## [0.1.1] - 2026-05-11

### Fixed
- `get_comparables` now calls the correct endpoint
  `GET /api/comparables/{uprn}/` (path parameter) instead of
  `GET /api/comparables/?uprn=` which returns 404. The unused `radius_m`
  argument has been replaced with `count` (1-200, default 20) to match the
  API contract — comparables are returned by geographic proximity, not by a
  fixed radius.

### Changed
- `lookup_council_tax` now returns a clear "in development" response without
  hitting the API. The underlying `/api/council_tax_band/` endpoint is
  documented as coming-soon and currently 404s for almost all UPRNs; the
  short-circuit prevents wasted credits and confusing errors. The tool will
  start returning live data once the endpoint ships — see
  https://homedata.co.uk/changelog.
- `User-Agent` header now tracks the installed package version dynamically.

## [0.1.0] - 2026-05-04

Initial public release on PyPI.

### Added
- 16 MCP tools wrapping the Homedata UK property data API:
  `lookup_property`, `lookup_epc`, `lookup_flood_risk`, `lookup_council_tax`,
  `search_property_listings`, `get_comparables`, `get_planning_applications`,
  `get_demographics`, `get_crime`, `get_schools`, `get_broadband`,
  `get_transport`, `get_postcode_profile`, `search_address`,
  `get_property_sales`, `batch_property_lookup`.
- `homedata-mcp` console entry point speaking MCP over stdio.
- `HomedataClient` async wrapper around the REST API with auth, timeouts and
  uniform error handling.
- Configurable via `HOMEDATA_API_KEY` and optional `HOMEDATA_BASE_URL`
  environment variables.
- Pytest suite that auto-skips when no API key is present.
