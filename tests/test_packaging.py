"""Things that go stale quietly: the version strings and the README's tool table."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import homedata_mcp

ROOT = Path(__file__).resolve().parent.parent


def test_version_strings_match():
    pyproject = (ROOT / "pyproject.toml").read_text()
    declared = re.search(r'^version = "([^"]+)"', pyproject, re.MULTILINE).group(1)
    assert homedata_mcp.__version__ == declared


def test_readme_tool_table_is_current():
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "readme_tools.py"), "--check"],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


def test_readme_makes_no_stale_offer():
    from homedata_mcp.parity import BANNED

    text = (ROOT / "README.md").read_text()
    for label, pattern in BANNED:
        assert not pattern.search(text), f"README contains {label}: {pattern.search(text).group(0)!r}"


def test_every_documented_cli_command_parses():
    """A README command that fails at argument parsing is worse than no example.

    `--term-years 25` survived the term_years rename and exited 2 for anyone who
    copied it. CodeRabbit caught that one; this catches the next, because the
    rename that breaks an example is never the rename you are thinking about.

    Parses only — it never calls the API, so it needs no key and spends nothing.
    A tool name that stops existing fails here too, as an invalid choice.

    Not covered: whether the arguments are SENSIBLE (a valid UPRN, a real
    postcode), only that the command is well formed. And only fenced lines that
    start with `homedata `, so a command wrapped mid-line is invisible to it.
    """
    import shlex
    from homedata_mcp import cli

    readme = (ROOT / "README.md").read_text()
    commands = [line.split("#")[0].strip() for line in readme.splitlines()
                if line.strip().startswith("homedata ")]

    assert len(commands) >= 3, "the scan found too few commands to mean anything"

    broken = []
    for command in commands:
        try:
            cli.build_parser().parse_args(shlex.split(command)[1:])
        except SystemExit:
            broken.append(command)

    assert broken == [], "README commands that fail to parse:\n" + "\n".join(broken)
