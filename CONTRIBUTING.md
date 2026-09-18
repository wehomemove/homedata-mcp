# Contributing

## The tool list comes from the Playground

The MCP offers exactly the self-serve endpoints of the Homedata Developer
Playground. Do not add, remove or reshape a tool by hand: change the
Playground catalogue in thor, then regenerate.

```bash
git -C <thor clone> fetch origin
node scripts/generate-manifest.mjs --thor <thor clone> --ref origin/main
python scripts/readme_tools.py
pytest
```

- `homedata_mcp/manifest/tools.json` is generated. The generator exits 2 if
  the Playground's cost or path code has a rule it does not know; encode the
  rule in `scripts/manifest-config.json` and run it again.
- A new tool needs a description in `homedata_mcp/manifest/descriptions.json`
  (the price in tokens must be stated) and help for any new argument name in
  `param_descriptions.json`. The tests say which are missing.
- `node scripts/generate-manifest.mjs --thor <thor clone> --init-descriptions`
  writes a stub for each new tool; replace it with real copy.

## What the tests enforce

- `tests/test_server_parity.py`: the server's tools, arguments, requests and
  stated prices match the manifest, and the signup helpers call nothing.
- `tests/test_stdio_smoke.py`: a real MCP client session over stdio, against
  a local stand-in for the API.
- `.github/workflows/drift.yml` (weekly): the manifest still matches the
  public Playground catalogue at https://homedata.co.uk/llms-full.txt, and every
  query key in the manifest is a parameter loki's live schema declares.

## The schema check, and why a key can be wrong while everything is green

`scripts/check_schema_params.py` compares the manifest's query keys with loki's
live OpenAPI schema. It exists because nothing else did: the parity guard compares
the server with the manifest, the drift check compares the manifest with the
published catalogue, and a key the catalogue sends that loki quietly ignores
satisfies both. That is how `calc_mortgage` came to send `term_years`, which loki
drops, returning a confident 25-year answer whatever term you ask for.

It is **expected to fail today** on exactly two keys, `calc_mortgage.term_years`
and `schools.radius`. Both are catalogue defects being fixed at source; when that
lands, regenerate the manifest and the check goes green. Do not silence them here.

A key the schema does not declare can also be a schema that under-declares, so an
exception is possible — per key, in `homedata_mcp/manifest/schema_exceptions.json`,
naming the one key and citing the measurement or source that justifies it. There
is deliberately no way to exempt a tool, a path or a file: a carve-out whose
reason cannot be written per key is too broad, and inherits nothing when a key is
added later. Run it before a release; it is required green apart from the two
known keys above.

## Releasing

Publishing needs a go from the product owner. When there is one:

1. Set the version in `pyproject.toml` and `homedata_mcp/__init__.py` (a test
   checks they match) and date the CHANGELOG entry.
2. Merge to `main` with CI green.
3. Push a tag `vX.Y.Z`. `.github/workflows/release.yml` builds and publishes
   to PyPI through trusted publishing; no token is involved.
