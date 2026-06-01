# Homedata MCP Server

A [Model Context Protocol](https://modelcontextprotocol.io) server that exposes
the [Homedata](https://homedata.co.uk) UK property data API as native tools for
AI coding assistants - Claude Desktop, Claude Code, Cursor, and any other MCP
client.

29M UK addresses keyed by UPRN, with EPCs, sale history, planning, flood risk,
council tax, demographics, crime, schools, broadband and transport - all
queryable directly from your assistant chat.

> Data is sourced from Home.co.uk's 30-year panel of partners, the Environment
> Agency, ONS Census 2021, the Valuation Office Agency, Ofcom, Ofsted,
> data.police.uk and HM Land Registry.

---

## Install

Requires Python 3.10+.

```bash
pip install homedata-mcp
```

For local development from this repository:

```bash
git clone https://github.com/wehomemove/homedata-mcp.git
cd homedata-mcp
pip install -e .
```

You will need a Homedata API key. Sign up at
[homedata.co.uk/developer](https://homedata.co.uk/developer) - the Free tier
gives 100 calls / month with no card required.

```bash
export HOMEDATA_API_KEY=hd_live_xxx
homedata-mcp --help
```

---

## CLI

The package also installs a `homedata` command — same data as the MCP
server but for human shells, scripting, and CI. Useful for quick lookups,
demos, and piping into other tools.

```bash
homedata property 100021421083
homedata epc 100021421083 --field current_energy_efficiency
homedata search "10 downing street" --postcode SW1A2AA
homedata flood 100021421083 --compact
homedata batch 100021421083 100022121211
```

Pass `--field <dotted.path>` to extract a single value (handy for shell
pipelines) and `--compact` for single-line JSON. Reads the same
`HOMEDATA_API_KEY` env var as the MCP server. Run `homedata --help` for
the full list of subcommands.

---

## Wire it into Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`
(macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "homedata": {
      "command": "homedata-mcp",
      "env": {
        "HOMEDATA_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

Restart Claude Desktop. You should see the 16 Homedata tools appear in the
tool picker.

### Cursor / Claude Code

Both Cursor and Claude Code accept the same MCP server spec. Add an entry
pointing `command` at `homedata-mcp` and put your key in `env`.

---

## Tools

All UPRN tools take a single 12-digit Unique Property Reference Number; all
postcode tools accept any common UK postcode format.

### Property tiers — pick a depth

One UPRN in, fixed cost out. Choose the cheapest tier that covers what
you need; `discover_property` is the 1-call menu that tells you which
slugs are populated before you commit.

| Tool | Endpoint | Cost | What it returns |
|------|----------|------|-----------------|
| `discover_property` | `GET /property/{uprn}/` | 1 call | The menu — which slugs exist for this UPRN + tier shortcuts |
| `lookup_property_address` | `GET /property/{uprn}/address` | 5 calls | Address + identifiers only |
| `lookup_property_base` | `GET /property/{uprn}/base` | 10 calls | Address + rooms + EPC + last sold + construction + dimensions + garden + parking + LR title basics |
| `lookup_property_core` ⭐ | `GET /property/{uprn}/core` | 25 calls | **Recommended.** Base + council tax + flood + schools + broadband + crime + demographics + amenities + planning summary + valuations + solar + lr_sales |
| `lookup_property_complete` | `GET /property/{uprn}/complete` | 50 calls | Core + council tax full (£ charges) + comparables + live listings + full risks + deprivation + planning history + price trends |

### Single-purpose lookups

| Tool | Endpoint | Inputs |
|------|----------|--------|
| `lookup_property` | `GET /properties/{uprn}/` | `uprn` — legacy single-call detail; prefer the tier tools above |
| `lookup_epc` | `GET /epc-checker/{uprn}/` | `uprn` |
| `lookup_flood_risk` | `GET /flood-risk/?uprn=` | `uprn` |
| `lookup_council_tax_band` | `GET /council_tax_band/{uprn}/` | `uprn` — band + authority, 3 calls |
| `lookup_council_tax` | `GET /council_tax/{uprn}/` | `uprn` — band + authority + yearly/monthly £, 5 calls |
| `search_property_listings` | `GET /property_listings/?uprn=` | `uprn` |
| `get_comparables` | `GET /comparables/{uprn}/?count=` | `uprn`, `count` (default 20, max 200) |
| `get_planning_applications` | `GET /planning/search/?uprn=` | `uprn` |
| `get_demographics` | `GET /demographics/?postcode=` | `postcode` |
| `get_crime` | `GET /crime/?postcode=` | `postcode`, `date` (YYYY-MM, optional) |
| `get_schools` | `GET /schools/?uprn=&radius_m=` | `uprn`, `radius_m` (default 1000) |
| `get_broadband` | `GET /broadband/?postcode=` | `postcode` |
| `get_transport` | `GET /transport/?uprn=&radius_m=` | `uprn`, `radius_m` (default 800) |
| `get_postcode_profile` | `GET /postcode-profile/?postcode=` | `postcode` |
| `search_address` | `GET /address/find/?q=` | `query`, `postcode` (optional) |
| `get_property_sales` | `GET /property_sales/?uprn=` | `uprn` |
| `batch_property_lookup` | `POST /property/batch/` | `uprns` (list, max 50) |

### Typical workflow

1. **Resolve text → UPRN** with `search_address`.
2. (Optional) `discover_property` to see what's available for the UPRN.
3. **Pick a tier**: `lookup_property_core` is the recommended starting
   point — one call gets you address, energy, statutory, area context
   and valuations in a single response. Step down to `_base` if you
   only need the basics; step up to `_complete` if you want comparables
   and full risks too.
4. For narrow follow-ups use the single-purpose tools (`lookup_council_tax`,
   `lookup_flood_risk`, `get_planning_applications`, etc.).
4. Add area context: `get_postcode_profile` (cheap one-shot), or call
   `get_demographics` / `get_crime` / `get_schools` / `get_broadband` /
   `get_transport` individually.

---

## Configuration

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `HOMEDATA_API_KEY` | yes | - | Your Homedata API key (`Authorization: Api-Key ...`). |
| `HOMEDATA_BASE_URL` | no | `https://api.homedata.co.uk` | Override for staging or self-hosted. |

Every tool returns either the parsed JSON body from the API, or
`{"error": "...", "status_code": N, "detail": ...}` on failure - tools never
raise exceptions out into the MCP protocol layer.

---

## Pricing

Calls made via this MCP server count against your Homedata API plan exactly
the same as any other API call. Plans (as of writing):

| Plan | Price | Calls / month |
|------|-------|---------------|
| Free | £0 | 100 |
| Starter | £49 | 2,000 |
| Growth | £149 | 10,000 |
| Pro | £349 | 50,000 |
| Scale | £699 | 250,000 |

See [homedata.co.uk/pricing](https://homedata.co.uk/pricing) for the current
list.

---

## Development

```bash
pip install -e ".[dev]"
HOMEDATA_API_KEY=hd_live_xxx pytest -v
```

Tests are skipped automatically when no API key is present, so the suite is
safe to run in CI without secrets.

### Project layout

```
homedata-mcp/
  pyproject.toml
  README.md
  homedata_mcp/
    __init__.py
    server.py           # FastMCP server + CLI entry point
    client.py           # httpx wrapper with auth + uniform error handling
    tools/
      __init__.py
      property.py       # lookup_property, batch_property_lookup
      epc.py            # lookup_epc
      risk.py           # lookup_flood_risk, lookup_council_tax
      listings.py       # search_property_listings, get_property_sales, get_comparables
      planning.py       # get_planning_applications
      local.py          # get_demographics, get_crime, get_schools, get_broadband, get_transport
      address.py        # search_address
      profile.py        # get_postcode_profile
  tests/
    test_tools.py
```

---

## License

MIT - see [LICENSE](LICENSE).
