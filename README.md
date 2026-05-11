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

| # | Tool | Endpoint | Inputs |
|---|------|----------|--------|
| 1 | `lookup_property` | `GET /api/properties/{uprn}/` | `uprn` |
| 2 | `lookup_epc` | `GET /api/epc-checker/{uprn}/` | `uprn` |
| 3 | `lookup_flood_risk` | `GET /api/flood-risk/?uprn=` | `uprn` |
| 4 | `lookup_council_tax` | _in development — returns a "coming soon" response_ | `uprn` |
| 5 | `search_property_listings` | `GET /api/property_listings/?uprn=` | `uprn` |
| 6 | `get_comparables` | `GET /api/comparables/{uprn}/?count=` | `uprn`, `count` (default 20, max 200) |
| 7 | `get_planning_applications` | `GET /api/planning/search/?uprn=` | `uprn` |
| 8 | `get_demographics` | `GET /api/demographics/?postcode=` | `postcode` |
| 9 | `get_crime` | `GET /api/crime/?postcode=` | `postcode`, `date` (YYYY-MM, optional) |
| 10 | `get_schools` | `GET /api/schools/?uprn=&radius_m=` | `uprn`, `radius_m` (default 1000) |
| 11 | `get_broadband` | `GET /api/broadband/?postcode=` | `postcode` |
| 12 | `get_transport` | `GET /api/transport/?uprn=&radius_m=` | `uprn`, `radius_m` (default 800) |
| 13 | `get_postcode_profile` | `GET /api/postcode-profile/?postcode=` | `postcode` |
| 14 | `search_address` | `GET /api/address/find/?q=` | `query`, `postcode` (optional) |
| 15 | `get_property_sales` | `GET /api/property_sales/?uprn=` | `uprn` |
| 16 | `batch_property_lookup` | `POST /api/property/batch/` | `uprns` (list, max 50) |

### Typical workflow

1. **Resolve text → UPRN** with `search_address`.
2. Look up the property: `lookup_property`, `lookup_epc`,
   `lookup_council_tax`, `lookup_flood_risk`.
3. Add market context: `search_property_listings`, `get_property_sales`,
   `get_comparables`.
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
