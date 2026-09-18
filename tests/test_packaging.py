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
