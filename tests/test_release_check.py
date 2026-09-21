"""Proves release_check refuses, and refuses for the stated reason.

A composite check that says only "failed" is barely better than the prose it
replaces, so most of these assert WHICH gate is named and WHY — not merely that
the exit code was non-zero.

The three-outcome model is the point of the file. PASS, FAIL and UNKNOWN are
asserted as distinct: a gate that could not run must never be mistaken for one
that ran and was happy, and both must refuse.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("release_check", ROOT / "scripts" / "release_check.py")
release_check = importlib.util.module_from_spec(_spec)
# Registered before exec: @dataclass resolves its annotations through
# sys.modules[cls.__module__], which is None for a module loaded by path alone.
sys.modules["release_check"] = release_check
_spec.loader.exec_module(release_check)

PASS = release_check.PASS
FAIL = release_check.FAIL
UNKNOWN = release_check.UNKNOWN
Result = release_check.Result


def _run_returns(monkeypatch, code, output=""):
    monkeypatch.setattr(release_check, "_run", lambda *a, **k: (code, output))


# --- the three-outcome contract ---------------------------------------------


def test_all_pass_is_the_only_zero_exit():
    results = [Result("a", PASS, ""), Result("b", PASS, "")]
    assert release_check.exit_code(results) == 0


def test_a_failed_gate_exits_one():
    assert release_check.exit_code([Result("a", PASS, ""), Result("b", FAIL, "")]) == 1


def test_an_undetermined_gate_refuses_too_and_is_distinct_from_a_failure():
    # The whole reason this file exists: "could not check" must not read as "fine".
    results = [Result("a", PASS, ""), Result("b", UNKNOWN, "")]
    assert release_check.exit_code(results) == 2, "an unreachable gate must refuse"
    assert release_check.exit_code(results) != 0


def test_a_failure_outranks_an_unknown_in_the_exit_code():
    results = [Result("a", UNKNOWN, ""), Result("b", FAIL, "")]
    assert release_check.exit_code(results) == 1


# --- the schema gate, which is what the script is built around ---------------


def test_schema_gate_names_every_undeclared_key(monkeypatch):
    _run_returns(monkeypatch, 1, "\n".join([
        "schools.radius: not a declared parameter of /schools/nearby (declared: lat, lng)",
        "calc_mortgage.term_years: not a declared parameter of /calculators/mortgage/ (declared: term)",
        "",
        "2 key(s) the schema does not declare. Either the catalogue sends a key loki ignores...",
    ]))
    result = release_check.gate_schema()

    assert result.outcome == FAIL
    # Named, not counted. A refusal whose members are not shown cannot be acted on.
    assert "schools.radius" in result.detail
    assert "calc_mortgage.term_years" in result.detail


def test_schema_gate_refuses_the_known_keys_rather_than_excusing_them(monkeypatch):
    # CONTRIBUTING.md calls these two "known" and says the check is required green
    # "apart from" them. That carve-out is the loophole this script closes: a
    # known key still ships a tool that answers confidently and wrongly.
    _run_returns(monkeypatch, 1, "calc_mortgage.term_years: not a declared parameter of /calculators/mortgage/")
    result = release_check.gate_schema()

    assert result.outcome == FAIL, "a known-but-unfixed key must still refuse the release"
    assert "known is not the same as acceptable" in result.detail


def test_schema_gate_is_unknown_when_the_live_schema_cannot_be_read(monkeypatch):
    # check_schema_params exits 2 when it cannot reach its source of truth.
    _run_returns(monkeypatch, 2, "could not check the manifest against the schema: <urlopen error>")
    result = release_check.gate_schema()

    assert result.outcome == UNKNOWN
    assert result.outcome != PASS


def test_schema_gate_is_unknown_when_the_checker_will_not_run(monkeypatch):
    monkeypatch.setattr(release_check, "_run", lambda *a, **k: (None, "python is not installed"))
    assert release_check.gate_schema().outcome == UNKNOWN


def test_schema_gate_passes_only_on_a_zero_exit(monkeypatch):
    _run_returns(monkeypatch, 0, "in step: 96 query keys across 56 tools are declared or cited")
    assert release_check.gate_schema().outcome == PASS


# --- the other network gate --------------------------------------------------


def test_drift_gate_separates_unreachable_from_drifted(monkeypatch):
    _run_returns(monkeypatch, 2, "could not fetch the catalogue")
    assert release_check.gate_drift().outcome == UNKNOWN

    _run_returns(monkeypatch, 1, "3 tools are not in the published catalogue")
    assert release_check.gate_drift().outcome == FAIL


# --- the local gates ---------------------------------------------------------


def _tree(tmp_path: Path, version: str = "1.0.0", init_version: str | None = None,
          changelog: str | None = None) -> Path:
    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nname = "homedata-mcp"\nversion = "{version}"\n', encoding="utf-8")
    package = tmp_path / "homedata_mcp"
    package.mkdir(exist_ok=True)
    (package / "__init__.py").write_text(
        f'__version__ = "{init_version or version}"\n', encoding="utf-8")
    if changelog is not None:
        (tmp_path / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    return tmp_path


PYPROJECT_WITH_A_DECOY = """\
[build-system]
requires = ["setuptools"]

[project]
name = "homedata-mcp"
version = "1.0.0"

[tool.some-other-tool]
version = "9.9.9"
"""


@pytest.mark.parametrize("no_tomllib", [False, True], ids=["tomllib", "python3.10-fallback"])
def test_pyproject_version_read_the_same_way_with_and_without_tomllib(monkeypatch, no_tomllib):
    """The 3.10 path is exercised here, not trusted because 3.13 is green.

    tomllib is 3.11+, and this package supports 3.10. The first version of this
    script imported it unconditionally: green on my machine, ModuleNotFoundError
    on the 3.10 runner.
    """
    if no_tomllib:
        monkeypatch.setattr(release_check, "tomllib", None)

    assert release_check._pyproject_version(PYPROJECT_WITH_A_DECOY) == "1.0.0"


def test_the_fallback_does_not_pick_up_a_version_from_another_table(monkeypatch):
    # The obvious fallback — match any `^version = "..."` — would return 9.9.9
    # here if [tool.some-other-tool] came first, then compare two wrong strings
    # and report a pass. Scoped to [project] instead.
    monkeypatch.setattr(release_check, "tomllib", None)
    reordered = """\
[tool.some-other-tool]
version = "9.9.9"

[project]
name = "homedata-mcp"
version = "1.0.0"
"""
    assert release_check._pyproject_version(reordered) == "1.0.0"


@pytest.mark.parametrize("no_tomllib", [False, True], ids=["tomllib", "python3.10-fallback"])
def test_an_unreadable_pyproject_is_undetermined_not_guessed(monkeypatch, no_tomllib):
    if no_tomllib:
        monkeypatch.setattr(release_check, "tomllib", None)

    assert release_check._pyproject_version("[project]\nname = \"x\"\n") is None
    assert release_check._pyproject_version("not toml at all {{{") is None


def test_versions_gate_fails_when_the_two_strings_disagree(monkeypatch, tmp_path):
    monkeypatch.setattr(release_check, "ROOT", _tree(tmp_path, "1.0.0", init_version="0.9.0"))
    result = release_check.gate_versions()

    assert result.outcome == FAIL
    assert "1.0.0" in result.detail and "0.9.0" in result.detail


def test_versions_gate_passes_when_they_agree(monkeypatch, tmp_path):
    monkeypatch.setattr(release_check, "ROOT", _tree(tmp_path, "1.0.0"))
    assert release_check.gate_versions().outcome == PASS


def test_versions_gate_is_unknown_when_pyproject_is_unreadable(monkeypatch, tmp_path):
    monkeypatch.setattr(release_check, "ROOT", tmp_path)  # nothing in it
    assert release_check.gate_versions().outcome == UNKNOWN


def test_changelog_gate_fails_while_the_entry_says_unreleased(monkeypatch, tmp_path):
    monkeypatch.setattr(release_check, "ROOT",
                        _tree(tmp_path, changelog="# Changelog\n\n## [1.0.0] - unreleased\n\nA rebuild.\n"))
    result = release_check.gate_changelog("1.0.0")

    assert result.outcome == FAIL
    assert "unreleased" in result.detail


def test_changelog_gate_fails_when_the_version_has_no_entry(monkeypatch, tmp_path):
    monkeypatch.setattr(release_check, "ROOT",
                        _tree(tmp_path, changelog="# Changelog\n\n## [0.2.0] - 2026-05-01\n"))
    assert release_check.gate_changelog("1.0.0").outcome == FAIL


def test_changelog_gate_fails_on_an_undated_entry(monkeypatch, tmp_path):
    monkeypatch.setattr(release_check, "ROOT",
                        _tree(tmp_path, changelog="# Changelog\n\n## [1.0.0]\n\nStuff.\n"))
    assert release_check.gate_changelog("1.0.0").outcome == FAIL


def test_changelog_gate_passes_on_a_dated_entry(monkeypatch, tmp_path):
    monkeypatch.setattr(release_check, "ROOT",
                        _tree(tmp_path, changelog="# Changelog\n\n## [1.0.0] - 2026-09-18\n\nStuff.\n"))
    assert release_check.gate_changelog("1.0.0").outcome == PASS


def test_changelog_gate_is_unknown_when_the_version_could_not_be_read():
    # Not a pass, and not a failure of the changelog either: unknown propagates.
    assert release_check.gate_changelog(None).outcome == UNKNOWN


def test_tag_gate_fails_when_the_tag_already_exists(monkeypatch):
    _run_returns(monkeypatch, 0, "v1.0.0")
    result = release_check.gate_tag_is_free("1.0.0")

    assert result.outcome == FAIL
    assert "already a tag" in result.detail


def test_tag_gate_passes_when_the_tag_is_free(monkeypatch):
    _run_returns(monkeypatch, 0, "")
    assert release_check.gate_tag_is_free("1.0.0").outcome == PASS


def test_tag_gate_is_unknown_when_git_will_not_run(monkeypatch):
    monkeypatch.setattr(release_check, "_run", lambda *a, **k: (None, "git: not found"))
    assert release_check.gate_tag_is_free("1.0.0").outcome == UNKNOWN


def test_clean_tree_gate_fails_on_uncommitted_work(monkeypatch):
    _run_returns(monkeypatch, 0, " M homedata_mcp/server.py\n?? scratch.py")
    result = release_check.gate_clean_tree()

    assert result.outcome == FAIL
    assert "2 uncommitted change(s)" in result.detail


def test_clean_tree_gate_passes_on_a_clean_tree(monkeypatch):
    _run_returns(monkeypatch, 0, "")
    assert release_check.gate_clean_tree().outcome == PASS


def test_manifest_gate_is_unknown_without_a_thor_checkout_never_skipped():
    result = release_check.gate_manifest_current(None)

    assert result.outcome == UNKNOWN, "a gate that cannot run must refuse, not be skipped"
    assert "--thor" in result.detail


def test_manifest_gate_is_unknown_when_the_path_is_not_a_checkout(tmp_path):
    assert release_check.gate_manifest_current(str(tmp_path)).outcome == UNKNOWN


def test_manifest_gate_fails_when_the_committed_manifest_is_stale(monkeypatch, tmp_path):
    (tmp_path / ".git").mkdir()
    _run_returns(monkeypatch, 1, "tools.json is stale against thor abc1234; regenerate")
    result = release_check.gate_manifest_current(str(tmp_path))

    assert result.outcome == FAIL
    assert "stale" in result.detail


# --- offline can never produce a go ------------------------------------------


def test_offline_marks_the_network_gates_undetermined_rather_than_omitting_them(monkeypatch):
    monkeypatch.setattr(release_check, "gate_versions", lambda: Result("versions", PASS, ""))
    monkeypatch.setattr(release_check, "gate_tag_is_free", lambda v: Result("tag-free", PASS, ""))
    monkeypatch.setattr(release_check, "gate_changelog", lambda v: Result("changelog", PASS, ""))
    monkeypatch.setattr(release_check, "gate_clean_tree", lambda: Result("clean-tree", PASS, ""))
    monkeypatch.setattr(release_check, "gate_parity", lambda: Result("parity", PASS, ""))
    monkeypatch.setattr(release_check, "gate_manifest_current", lambda t: Result("manifest", PASS, ""))

    results = release_check.collect(thor="/anywhere", offline=True)
    by_gate = {r.gate: r for r in results}

    assert by_gate["drift"].outcome == UNKNOWN
    assert by_gate["schema"].outcome == UNKNOWN
    assert release_check.exit_code(results) == 2, "--offline must never be able to say go"


# --- the output a human reads ------------------------------------------------


@pytest.mark.parametrize("failing", ["versions", "changelog", "schema", "manifest", "parity"])
def test_a_refusal_names_the_gate_that_refused(failing):
    """Fail exactly one gate at a time; the summary must name THAT gate.

    This is the partial proof, mechanised. A composite that reports only
    "something failed" sends a reader back to running the gates by hand, which is
    the situation this script was written to end.
    """
    results = [Result(gate, FAIL if gate == failing else PASS, "detail")
               for gate in ("versions", "changelog", "schema", "manifest", "parity")]
    rendered = release_check.render(results)

    assert "NO GO" in rendered
    assert failing in rendered.split("FAILED (determined to be wrong):")[1]
    for other in ("versions", "changelog", "schema", "manifest", "parity"):
        if other != failing:
            assert other not in rendered.split("FAILED (determined to be wrong):")[1].split("\n")[0]


def test_the_summary_separates_failed_from_undetermined():
    rendered = release_check.render([
        Result("schema", FAIL, "two keys"),
        Result("manifest", UNKNOWN, "no thor checkout"),
    ])

    assert "FAILED (determined to be wrong):" in rendered
    assert "UNDETERMINED (could not be checked):" in rendered
    # The distinction is only useful if a reader is told it matters.
    assert "An undetermined gate is not a passing one" in rendered


def test_a_full_pass_says_go_and_still_names_what_it_does_not_cover():
    rendered = release_check.render([Result("a", PASS, "fine"), Result("b", PASS, "fine")])

    assert "GO — all 2 gates pass" in rendered
    assert "product owner" in rendered, "a green check is not permission to publish"
    assert "CI must be green" in rendered


def test_docstring_carries_the_rule_the_whole_script_rests_on():
    assert 'DISTINCT, LOUD OUTCOME' in release_check.__doc__.upper()


def test_a_truncated_tail_says_it_truncated():
    """Silent truncation is how a partial list is read as a whole one.

    `pint --test` elides its fixer list at the terminal width with nothing but an
    ellipsis; a reviewer read one fixer where there were four, and the hidden one
    rewrote an expression rather than reformatting it. Several gates here print a
    count beside this list, so an unmarked cut would show "20 changes" above eight
    lines and look complete.
    """
    output = "\n".join(f"line {n}" for n in range(1, 21))
    shown = release_check._tail(output, 8)

    assert "[12 earlier line(s) not shown]" in shown
    assert "line 20" in shown and "line 13" in shown
    assert "line 12" not in shown.replace("[12 earlier line(s) not shown]", "")
    # The marker trails the content: the summary renders a result's FIRST line,
    # so a leading marker replaced "64 passed" with the marker on every pass.
    assert shown.splitlines()[0] == "line 13"
    assert shown.splitlines()[-1].startswith("[12 earlier")


def test_an_untruncated_tail_claims_no_truncation():
    # The marker must not appear when nothing was cut, or it stops being a signal.
    shown = release_check._tail("one\ntwo\nthree", 8)

    assert "not shown" not in shown
    assert shown == "one\ntwo\nthree"


def test_the_clean_tree_gate_count_and_its_list_cannot_disagree_silently(monkeypatch):
    # The specific shape: a count printed beside a truncated list.
    _run_returns(monkeypatch, 0, "\n".join(f" M file{n}.py" for n in range(1, 21)))
    detail = release_check.gate_clean_tree().detail

    assert "20 uncommitted change(s)" in detail
    assert "not shown" in detail, "a count above a cut list must say it was cut"
