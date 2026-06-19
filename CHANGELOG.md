# Changelog

All notable changes to `homedata-mcp` will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0] - 2026-06-19

### Added — broad endpoint coverage

Wraps every remaining public Homedata endpoint as a first-class MCP tool.
Grouped into four new modules:

**`valuation`**
- `estimate_valuation(uprn, type, ...)` — AVM sale/rent estimate with
  confidence range (`/valuations/estimate/`).
- `get_avm_comparables(uprn, count)` — the comparable set behind an AVM
  estimate (`/avm/`).
- `get_lr_sales(uprn?, sale?)` — HM Land Registry price-paid records
  (`/lr-sales/`).

**`area`**
- `get_deprivation(postcode)` — IMD rank/decile + domain scores
  (`/deprivation/`).
- `get_conservation_areas(postcode, ...)` — `/conservation-areas/`.
- `get_listed_buildings(postcode, ...)` — `/listed-buildings/`.
- `get_planning_designations(postcode, ...)` — `/planning-designations/`.
- `get_price_trends(outcode)` — `/price_trends/{outcode}/`.
- `get_price_distribution(outcode)` — `/price_distributions/{outcode}/`.
- `get_price_growth(outcode)` — `/price-growth/{outcode}/`.
- `get_addresses_at_postcode(postcode)` — every address + UPRN at a
  postcode (`/address/postcode/{postcode}/`).

**`environment`**
- `get_solar_assessment(uprn)` — rooftop solar PV potential
  (`/solar-assessment/{uprn}/`).
- `get_risks(risk_type, uprn)` — one named hazard in depth: noise, flood,
  radon, landfill, coal_mining, invasive_plants, air_quality_today, or all
  (`/risks/{risk_type}/`).
- `get_energy(...)` — nearby energy infrastructure (`/energy/`).
- `get_brownfield(...)` — brownfield land registers (`/brownfield/`).
- `get_boreholes(...)` — BGS borehole logs (`/boreholes/`).
- `get_environment_report(...)` — consolidated environmental summary
  (`/environment-report/`).
- `get_rights_of_way(...)` — public rights of way (`/rights-of-way/`).

**`local_extra`**
- `get_amenities(...)` — nearby POIs (`/amenities/`).
- `get_fuel_stations(...)` — petrol/EV stations (`/fuel-stations/`).
- `get_healthcare(...)` — GPs, hospitals, pharmacies (`/healthcare/`).
- `get_agent_stats(uprn)` — estate-agent performance stats
  (`/agent_stats/{uprn}/`).
- `search_live_listings(...)` — filterable live on-market listings index
  (`/live-listings/search/`).

Spatial tools (`get_energy`, `get_brownfield`, `get_boreholes`,
`get_environment_report`, `get_rights_of_way`, `get_amenities`,
`get_fuel_stations`, `get_healthcare`) accept either a UPRN/title number
anchor or raw lat/lng. Optional filters are omitted from the querystring
when left unset.

No behaviour change to existing tools.

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
