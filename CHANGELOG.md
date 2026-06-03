# Changelog

All notable changes to `homedata-mcp` will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0] - 2026-06-03

### Changed

- **`DEFAULT_TIMEOUT_SECONDS` bumped from 10.0 to 60.0.** The 10-second
  default was too tight for the heavier endpoints — `get_postcode_profile`
  fans out ~10 parallel server-side sub-queries, `get_comparables` runs
  a cold PostGIS spatial scan, and a heavily-listed property in
  `search_property_listings` can take a few seconds to assemble. The
  Homedata API itself runs behind a 120s gunicorn worker timeout; the
  prior 10s cap was a purely client-side limit that was causing
  spurious timeouts on legitimate requests. New default gives realistic
  headroom while still failing fast on genuinely hung calls.

- Override per-client by passing `timeout=` to `HomedataClient(...)` —
  e.g. drop it back to 10s if you need very tight SLOs and only call
  the light tools.

### Improved — tool docstring guidance

Customers integrating via AI agents read the tool docstrings to pick
which tool to use and how to handle errors. Updated four tool
descriptions to embed performance and retry guidance directly:

- **`get_postcode_profile`** — notes the fan-out behaviour, expected
  timings (3-8s cold, <100ms cached for 24h), and documents the new
  `partial: true` / `timed_out_keys` response fields that the upstream
  Loki API returns when one sub-query misses its budget.

- **`get_comparables`** — calls out the cold-PostGIS-scan latency
  (5-10s first call, <100ms cached for 24h) and adds explicit retry
  guidance: "wait ~5 seconds and retry — by then the upstream cache
  has usually warmed."

- **`search_property_listings`** — notes the per-property assembly
  cost on long-history listings and that area-based search is on the
  roadmap.

- **`search_address`** — documents the matcher's query classifier
  behaviour with explicit DO / AVOID examples. The "street name + full
  postcode in one query string" pattern returns empty because the
  matcher tightens to an exact-postcode lookup; recommends using the
  dedicated `postcode=` parameter instead.

- **`batch_property_lookup`** — documents the per-row response shape
  (`found: true/false`, optional `error` field on transient per-row
  failures) and explicitly states that "a missing or broken UPRN does
  NOT 500 the whole batch" — so callers don't waste time pre-validating
  every UPRN. Pairs with the Loki-side per-row error containment fix
  shipping in `wehomemove/loki` PR #121.

### Why this release

Customer feedback 2026-06-03 (specific MCP integrator) flagged three
real issues: heavy endpoints timing out at our 10s client default,
`batch_property_lookup` apparently 500-ing on missing UPRNs (the Loki
fix is in PR #121 — server now correctly returns 200 with `found:
false` per row), and `search_address` returning empty for valid
"street + postcode" combinations. This release closes the docstring/UX
side of all three.

## [0.4.0] - 2026-06-01

### Added — Property tier tools

The new fixed-cost property tier endpoints get first-class MCP tools.
One UPRN in, fixed depth out, fixed cost — pick the cheapest tier that
covers what you need. Five new tools:

- `discover_property(uprn)` — 1 call. The menu: which slugs are
  populated for this UPRN, plus tier shortcut paths. Use this first to
  avoid paying for a tier whose slugs aren't all present.
- `lookup_property_address(uprn)` — 5 calls. Address + identifiers only.
- `lookup_property_base(uprn)` — 10 calls. Address + rooms + EPC +
  last sold + construction + dimensions + garden/parking + LR title.
- `lookup_property_core(uprn)` — 25 calls. **Recommended starting tier.**
  Base + council tax + flood + schools + broadband + crime + demographics
  + amenities + planning summary + valuations + solar + lr_sales.
- `lookup_property_complete(uprn)` — 50 calls. Core + comparables + live
  listings + full risks + deprivation + planning history + price trends.

`lookup_property` (legacy single-call /properties/{uprn}/) is preserved
for backward compatibility but the tier tools above are now the
recommended path.

### Added — Council tax tools (endpoints went live 2026-05-29)

Two new tools replace the 0.3.x "coming soon" stub:

- `lookup_council_tax_band(uprn)` — 3 calls. Band letter + billing
  authority. Cheap "just the band" lookup.
- `lookup_council_tax(uprn)` — 5 calls. Full bundle: band + authority +
  GSS code + country + yearly + monthly charge in £ + 1991 valuation
  band bounds + fiscal year label. All 4 UK nations, refreshed nightly.

The 0.3.x `lookup_council_tax` from `homedata_mcp.tools.risk` (which
returned a 503 "in development" placeholder) is removed. Council tax
tools moved to a dedicated `homedata_mcp.tools.council_tax` module.

### Changed

- **Endpoint paths no longer require the `/api/` prefix.** The Homedata
  API now serves every endpoint at the host root in addition to the
  legacy `/api/` prefix — e.g. `https://api.homedata.co.uk/properties/{uprn}/`
  instead of `https://api.homedata.co.uk/api/properties/{uprn}/`. Both
  URLs continue to work; this release switches the MCP client to the
  cleaner naked-host form. No behaviour change visible to MCP consumers
  — every tool returns the same response data, billing weight and call
  semantics are identical.

### Migration notes

- Existing deployments pointed at `HOMEDATA_BASE_URL=https://api.homedata.co.uk`
  keep working with no config change.
- AI agents that have already written code against `lookup_property` will
  keep working. New integrations should prefer the tier tools — fixed
  cost, better discount per slug, single round-trip.
- Self-hosted Homedata instances pinned to an older Loki build that
  doesn't include the naked-host URLconf twin (Loki PR #102, 2026-06-01)
  should stay on `homedata-mcp` 0.3.x until that PR lands on their
  deployment.

## [0.3.0] - 2026-05-19

### Added
- **Signup-only mode** — the server now starts when `HOMEDATA_API_KEY` is
  unset instead of bailing at startup. Two new tools register
  unconditionally so an AI coding assistant can bootstrap a brand-new user
  before they have an API key:
  - `start_homedata_signup(email?)` — returns the signup URL, free-tier
    details, and a numbered checklist of what the user needs to do to
    activate the rest of the tools.
  - `check_homedata_api_key()` — diagnostic that tells the AI agent
    whether the key is set, valid, or whether the user needs to restart
    the MCP server after setting it. Never echoes key material — only a
    6-character prefix for diagnosis.
- When the API key is missing, the data tools (`search_address`,
  `lookup_property`, etc.) are not registered. Existing behaviour for the
  configured case is unchanged — all 16 data tools register as before.

### Why
  Previously, installing `homedata-mcp` and starting the server before
  signing up for a key failed with a startup error and no guidance. New
  users now get a smooth path: install → start → AI agent calls
  `start_homedata_signup` → user follows the link → restart server →
  data tools available.

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
