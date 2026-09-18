#!/usr/bin/env python3
"""Render the README's tool table from the manifest.

    python scripts/readme_tools.py          rewrite the table in README.md
    python scripts/readme_tools.py --check  exit 1 if the table is stale (tests run this)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from homedata_mcp import calls

BEGIN, END = "<!-- BEGIN GENERATED: tools -->", "<!-- END GENERATED: tools -->"


def price(tokens: dict) -> str:
    if tokens.get("plus_with_addons"):
        return f"{tokens['default']} + add-ons"
    if tokens["default"] == 0:
        return "free"
    rules = "".join(f"; {w['tokens']} when `{w['param']}` is {' or '.join(w['in'])}" for w in tokens.get("when", []))
    return f"{tokens['default']}{rules}"


def render() -> str:
    rows = ["| Tool | Tokens | What it returns |", "|---|---|---|"]
    for spec in sorted(calls.tools(), key=lambda t: t["name"]):
        text = re.sub(r"\s*(Costs .*|Free: .*)$", "", calls.description_for(spec["name"]))
        rows.append(f"| `{spec['name']}` | {price(spec['tokens'])} | {text} |")
    for spec in calls.static_tools():
        text = calls.description_for(spec["name"])
        rows.append(f"| `{spec['name']}` | none | {text} |")
    return "\n".join([BEGIN, *rows, END])


def main(argv: list[str]) -> int:
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    start, end = text.index(BEGIN), text.index(END) + len(END)
    updated = text[:start] + render() + text[end:]
    if "--check" in argv:
        if updated != text:
            print("README tool table is stale: run python scripts/readme_tools.py", file=sys.stderr)
            return 1
        return 0
    readme.write_text(updated, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
