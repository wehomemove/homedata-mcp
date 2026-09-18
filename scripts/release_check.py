#!/usr/bin/env python3
"""One command that says whether this tree may be tagged. Exits non-zero unless it may.

The release gates existed as separate commands someone had to remember to run in
the right order, which is the same as not having them. This composes them; it
re-implements none of them, so a gate's logic lives in exactly one place still.

    python scripts/release_check.py                      # everything reachable
    python scripts/release_check.py --thor ../thor-quinn # + the manifest gate
    python scripts/release_check.py --offline            # skip nothing, refuse loudly

Exit 0: every gate passed and the tree may be tagged.
Exit 1: a gate FAILED — something is wrong and the release must not go.
Exit 2: a gate could not be DETERMINED — no network, a missing file, a tool that
        would not run. Also a refusal.

"COULD NOT DETERMINE" MUST BE A DISTINCT, LOUD OUTCOME FROM "DETERMINED THAT IT
IS FINE." Every gate composed here has, somewhere in its history, a
green-for-the-wrong-reason story: a guard that passed because it could not reach
its source, a count whose members were never shown, a check whose output was
swallowed by a pipeline. A release check that passes because it could not check
is the worst possible version of this tool. Hence three outcomes, never two, and
UNKNOWN refuses exactly as hard as FAIL while reading differently.

THE SCHEMA GATE REFUSES ON ANY UNDECLARED KEY, INCLUDING THE TWO KNOWN ONES.
CONTRIBUTING.md says the schema check is "required green apart from the two known
keys", `calc_mortgage.term_years` and `schools.radius`. That carve-out is the
exact loophole this script exists to close: `term_years` is not a documentation
problem, it is a tool that answers every mortgage as 25 years whatever term you
ask for, and publishing it is the specific thing that must not happen. Known is
not the same as acceptable to ship. A key is silenced by fixing it at source and
regenerating, or by a cited per-key entry in schema_exceptions.json — never by
this script agreeing to look away.

WHAT THIS DOES NOT COVER:
  - Tagging or publishing. It reports go/no-go; a human still pushes the tag, and
    a publish still needs the product owner's go.
  - Whether a gate's own logic is right. Each has its own tests; this only runs
    them and reports honestly.
  - The Node package. Separate repository, separate release, separate check.
  - Whether the version number is the RIGHT one. It checks the strings agree with
    each other, not that 1.0.0 is the correct next version.
  - CI. A green run here is not a green run on the runner, and step 2 of
    CONTRIBUTING's release list still stands.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PASS = "PASS"
FAIL = "FAIL"
UNKNOWN = "UNKNOWN"


@dataclass
class Result:
    """One gate's verdict. `detail` is shown whatever the outcome, so a pass is auditable too."""

    gate: str
    outcome: str
    detail: str

    @property
    def refuses(self) -> bool:
        return self.outcome != PASS


def _run(command: list[str], cwd: Path = ROOT, timeout: int = 600) -> tuple[int | None, str]:
    """Run a command, returning (exit code, combined output). None means it could not run at all."""
    try:
        completed = subprocess.run(
            command, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False,
        )
    except FileNotFoundError as exc:
        return None, f"{command[0]} is not installed or not on PATH: {exc}"
    except subprocess.TimeoutExpired:
        return None, f"timed out after {timeout}s: {' '.join(command)}"
    except OSError as exc:  # pragma: no cover - environment specific
        return None, f"could not run {' '.join(command)}: {exc}"
    return completed.returncode, (completed.stdout + completed.stderr).strip()


def _tail(text: str, lines: int = 12) -> str:
    """Last few lines, for a failure message. Never used to establish a count or a set."""
    kept = [line for line in text.splitlines() if line.strip()]
    return "\n".join(kept[-lines:]) if kept else "(no output)"


# --- gates ------------------------------------------------------------------
# Each returns a Result and never raises: an exception here would be a check that
# could not check, reported as a crash rather than as UNKNOWN.


def gate_versions() -> Result:
    """pyproject.toml and homedata_mcp/__init__.py must agree."""
    try:
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        packaged = str(pyproject["project"]["version"])
    except (OSError, tomllib.TOMLDecodeError, KeyError, TypeError) as exc:
        return Result("versions", UNKNOWN, f"could not read the version from pyproject.toml: {exc}")

    try:
        source = (ROOT / "homedata_mcp" / "__init__.py").read_text(encoding="utf-8")
    except OSError as exc:
        return Result("versions", UNKNOWN, f"could not read homedata_mcp/__init__.py: {exc}")

    # Read the literal rather than importing: importing runs the package, which
    # pulls in dependencies a release machine may not have installed.
    found = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', source, re.MULTILINE)
    if not found:
        return Result("versions", UNKNOWN, "homedata_mcp/__init__.py declares no __version__")

    if found.group(1) != packaged:
        return Result("versions", FAIL,
                      f"pyproject.toml says {packaged}, homedata_mcp/__init__.py says {found.group(1)}")
    return Result("versions", PASS, f"both say {packaged}")


def gate_tag_is_free(version: str | None) -> Result:
    """The tag this release would push must not already exist."""
    if version is None:
        return Result("tag-free", UNKNOWN, "the version could not be read, so the tag cannot be checked")

    code, output = _run(["git", "tag", "--list", f"v{version}"])
    if code is None or code != 0:
        return Result("tag-free", UNKNOWN, f"could not list tags: {output}")
    if output.strip():
        return Result("tag-free", FAIL,
                      f"v{version} is already a tag. Bump the version, or the release workflow "
                      "republishes an existing one.")
    return Result("tag-free", PASS, f"v{version} is not yet tagged")


def gate_changelog(version: str | None) -> Result:
    """The CHANGELOG must carry a dated section for this version, not 'unreleased'."""
    if version is None:
        return Result("changelog", UNKNOWN, "the version could not be read, so its entry cannot be found")

    try:
        text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    except OSError as exc:
        return Result("changelog", UNKNOWN, f"could not read CHANGELOG.md: {exc}")

    heading = re.search(rf"^## \[{re.escape(version)}\][^\n]*", text, re.MULTILINE)
    if not heading:
        return Result("changelog", FAIL, f"CHANGELOG.md has no '## [{version}]' section")

    line = heading.group(0)
    if re.search(r"unreleased|tbd|todo", line, re.IGNORECASE):
        return Result("changelog", FAIL,
                      f"CHANGELOG.md still says {line.strip()!r}. Date the entry before tagging.")
    if not re.search(r"\d{4}-\d{2}-\d{2}", line):
        return Result("changelog", FAIL, f"{line.strip()!r} carries no YYYY-MM-DD date")
    return Result("changelog", PASS, line.strip())


def gate_clean_tree() -> Result:
    """A tag names a commit, so uncommitted work would not be in the release."""
    code, output = _run(["git", "status", "--porcelain"])
    if code is None or code != 0:
        return Result("clean-tree", UNKNOWN, f"could not read the working tree state: {output}")
    if output.strip():
        count = len(output.strip().splitlines())
        return Result("clean-tree", FAIL,
                      f"{count} uncommitted change(s); a tag would not include them:\n{_tail(output, 8)}")
    return Result("clean-tree", PASS, "no uncommitted changes")


def gate_parity() -> Result:
    """The server offers exactly the manifest, and sends exactly its requests."""
    code, output = _run([sys.executable, "-m", "pytest", "-q", "tests/test_server_parity.py"])
    if code is None:
        return Result("parity", UNKNOWN, f"the parity tests could not be run: {output}")
    if code != 0:
        return Result("parity", FAIL, f"the server and the manifest disagree:\n{_tail(output)}")
    return Result("parity", PASS, _tail(output, 1))


def gate_drift() -> Result:
    """The manifest still matches the published Playground catalogue."""
    code, output = _run([sys.executable, "scripts/check_drift.py"])
    if code is None:
        return Result("drift", UNKNOWN, f"the drift check could not be run: {output}")
    if code == 2:
        # check_drift's own contract: 2 means it could not reach its source.
        return Result("drift", UNKNOWN, f"the published catalogue could not be read:\n{_tail(output)}")
    if code != 0:
        return Result("drift", FAIL, f"the manifest and the published catalogue disagree:\n{_tail(output)}")
    return Result("drift", PASS, _tail(output, 1))


def gate_schema() -> Result:
    """Every query key the manifest sends is one loki's live schema declares.

    This is the gate the whole script is built around, so it names the offending
    keys rather than reporting a count or a tail.
    """
    code, output = _run([sys.executable, "scripts/check_schema_params.py"])
    if code is None:
        return Result("schema", UNKNOWN, f"the schema check could not be run: {output}")
    if code == 2:
        return Result("schema", UNKNOWN, f"loki's live schema could not be read:\n{_tail(output)}")
    if code != 0:
        # Name every key. A refusal whose members are not shown cannot be acted on,
        # and this refusal is the one a person will most want to argue with.
        keys = [line for line in output.splitlines() if re.match(r"^\S+\.\S+: ", line)]
        listed = "\n".join(f"    {key}" for key in keys) or f"    {_tail(output, 4)}"
        return Result("schema", FAIL, "\n".join([
            f"{len(keys)} query key(s) loki's schema does not declare:",
            listed,
            "",
            "    A key loki ignores is answered confidently and wrongly — term_years is why",
            "    every mortgage came back as 25 years. Fix it at source and regenerate, or",
            "    add a cited per-key exception. CONTRIBUTING.md calls two of these 'known';",
            "    known is not the same as acceptable to publish.",
        ]))
    return Result("schema", PASS, _tail(output, 1))


def gate_manifest_current(thor: str | None) -> Result:
    """Regenerating from the catalogue would produce the committed manifest."""
    if thor is None:
        return Result("manifest", UNKNOWN,
                      "needs a thor checkout to regenerate against: pass --thor <path>. "
                      "Not skipped — an ungenerated manifest is exactly how the catalogue and "
                      "the package drift apart.")
    path = Path(thor).expanduser()
    if not (path / ".git").exists():
        return Result("manifest", UNKNOWN, f"{path} is not a git checkout")

    code, output = _run(["node", "scripts/generate-manifest.mjs", "--thor", str(path), "--check"])
    if code is None:
        return Result("manifest", UNKNOWN, f"the generator could not be run: {output}")
    if code != 0:
        return Result("manifest", FAIL,
                      f"the committed manifest is not what the catalogue generates:\n{_tail(output)}")
    return Result("manifest", PASS, _tail(output, 1))


def _packaged_version() -> str | None:
    try:
        return str(tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"])
    except (OSError, tomllib.TOMLDecodeError, KeyError, TypeError):
        return None


def collect(thor: str | None, offline: bool) -> list[Result]:
    version = _packaged_version()
    results = [
        gate_versions(),
        gate_tag_is_free(version),
        gate_changelog(version),
        gate_clean_tree(),
        gate_parity(),
    ]
    if offline:
        # Named, not silently absent. --offline is for checking the local gates
        # quickly; it can never produce a go.
        results += [
            Result("drift", UNKNOWN, "--offline: the published catalogue was not read"),
            Result("schema", UNKNOWN, "--offline: loki's live schema was not read"),
        ]
    else:
        results += [gate_drift(), gate_schema()]
    results.append(gate_manifest_current(thor))
    return results


def render(results: list[Result]) -> str:
    width = max(len(r.gate) for r in results)
    lines = ["", "Release gates", "=" * 13, ""]
    for result in results:
        lines.append(f"  {result.outcome:<7} {result.gate:<{width}}  {result.detail.splitlines()[0]}")
        for extra in result.detail.splitlines()[1:]:
            lines.append(f"  {'':<7} {'':<{width}}  {extra}")
    failed = [r.gate for r in results if r.outcome == FAIL]
    unknown = [r.gate for r in results if r.outcome == UNKNOWN]
    lines.append("")
    if failed or unknown:
        lines.append("NO GO — do not tag this tree.")
        if failed:
            lines.append(f"  FAILED (determined to be wrong):        {', '.join(failed)}")
        if unknown:
            lines.append(f"  UNDETERMINED (could not be checked):    {', '.join(unknown)}")
            lines.append("  An undetermined gate is not a passing one. Make it checkable and re-run.")
    else:
        lines.append(f"GO — all {len(results)} gates pass. Tagging still needs the product owner's go,")
        lines.append("and CI must be green on main (CONTRIBUTING.md, Releasing, step 2).")
    lines.append("")
    return "\n".join(lines)


def exit_code(results: list[Result]) -> int:
    if any(r.outcome == FAIL for r in results):
        return 1
    if any(r.outcome == UNKNOWN for r in results):
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--thor", help="path to a thor checkout, for the manifest gate")
    parser.add_argument("--offline", action="store_true",
                        help="do not make network calls; the network gates report UNKNOWN and refuse")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    results = collect(args.thor, args.offline)
    if args.json:
        print(json.dumps([{"gate": r.gate, "outcome": r.outcome, "detail": r.detail} for r in results], indent=2))
    else:
        print(render(results))
    return exit_code(results)


if __name__ == "__main__":
    raise SystemExit(main())
