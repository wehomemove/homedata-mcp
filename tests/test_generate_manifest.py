"""Proves generate-manifest.mjs --check ignores the thor commit stamp and nothing else.

thor gets commits several times a day that never touch the Playground
catalogue. The check must not call tools.json stale for those, or a release tag
loses the race to every unrelated thor commit. Every other difference must
still fail: a tool field, a hand edit to tools.json, a catalogue edit that
leaves the tools the same, and a tools.json that records no commit at all.

Each test builds a throwaway thor repository with a minimal Index.vue and
llms-full.txt, and runs a copy of the generator against it so the real
homedata_mcp/manifest/tools.json is never touched.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not on PATH; generate-manifest.mjs needs Node")

VUE_PATH = "resources/js/Pages/Developer/Playground/Index.vue"
LLMS_PATH = "public/llms-full.txt"

INDEX_VUE = """<script setup>
// Playground catalogue (fixture for tests/test_generate_manifest.py)
const ENDPOINTS = [
    { id: 'address-find', label: 'Find an address', method: 'GET', path: '/address/find/',
      params: [{ name: 'q', type: 'text', required: true, hint: 'Part of an address' }] },
    { id: 'property-custom', label: 'Custom property', method: 'GET', path: '/property/:uprn/',
      params: [{ name: 'uprn', type: 'text', required: true, inPath: true }] },
    { id: 'risks', label: 'Risks', method: 'GET', path: '/risks/',
      params: [{ name: 'risk_type', type: 'text', options: ['all', 'flood:rivers'] }] },
    { id: 'listing-address', label: 'Listing address', method: 'POST', path: '/listing/address/',
      params: [{ name: 'listing_id', type: 'text', required: true }] },
    { id: 'property-sales', label: 'Sales', method: 'GET', path: '/sales/', adminOnly: true },
]

const ENDPOINT_WEIGHTS = { 'address-find': 0, 'property-custom': 1, 'risks': 1, 'listing-address': 2, 'property-sales': 1 }

const ENDPOINT_CREDIT_PENCE = {}

const NUMERIC_PARAM_NAMES = new Set(['uprn'])

const PROPERTY_ADDONS = [
    { id: 'epc', cost: 1 },
    { id: 'planning', cost: 2, comingSoon: true },
]

const estimatedCallCost = computed(() => {
    const ep = selected.value
    if (ep.id === 'property-custom') return builderTotalCost.value
    if (ep.id === 'risks') return form.risk_type === 'all' ? 5 : 1
    return ENDPOINT_WEIGHTS[ep.id]
})

const resolveEndpointPath = (ep) => {
    if (ep.id !== 'risks') return ep.path
    return ep.path
}
</script>
"""

LLMS_FULL = "<!-- BEGIN GENERATED: api-surface (source_hash: " + "ab" * 32 + ") -->\n"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _commit(repo: Path, files: dict[str, str], message: str) -> str:
    for rel, text in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.name=test", "-c", "user.email=test@example.invalid", "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def env(tmp_path):
    """A thor repo at commit A and a generator copy with tools.json generated at A."""
    thor = tmp_path / "thor"
    thor.mkdir()
    _git(thor, "init", "-q")
    commit_a = _commit(thor, {VUE_PATH: INDEX_VUE, LLMS_PATH: LLMS_FULL, "README.md": "thor\n"}, "A")

    root = tmp_path / "mcp"
    (root / "scripts").mkdir(parents=True)
    for name in ("generate-manifest.mjs", "manifest-config.json"):
        shutil.copy(ROOT / "scripts" / name, root / "scripts" / name)

    class Env:
        pass

    e = Env()
    e.thor, e.root, e.commit_a = thor, root, commit_a
    e.tools = root / "homedata_mcp" / "manifest" / "tools.json"
    e.run = lambda *args: subprocess.run(
        [NODE, str(root / "scripts" / "generate-manifest.mjs"), "--thor", str(thor), "--ref", "HEAD", *args],
        capture_output=True,
        text=True,
    )
    generated = e.run()
    assert generated.returncode == 0, generated.stderr
    assert json.loads(e.tools.read_text())["source"]["commit"] == commit_a
    return e


def test_check_passes_at_the_generated_commit(env):
    result = env.run("--check")
    assert result.returncode == 0, result.stderr
    assert f"current against thor {env.commit_a}" in result.stdout


def test_new_thor_commit_that_leaves_the_catalogue_alone_passes_and_names_both_commits(env):
    commit_b = _commit(env.thor, {"README.md": "thor, edited\n"}, "B: unrelated")
    result = env.run("--check")
    assert result.returncode == 0, result.stderr
    assert commit_b in result.stdout
    assert env.commit_a in result.stdout
    assert "only the recorded commit differs" in result.stdout


def test_changed_tool_field_fails(env):
    _commit(env.thor, {VUE_PATH: INDEX_VUE.replace("'Find an address'", "'Find addresses'")}, "B: label")
    result = env.run("--check")
    assert result.returncode == 1
    assert "stale" in result.stderr


def test_a_stale_check_names_both_commits(env):
    commit_b = _commit(env.thor, {VUE_PATH: INDEX_VUE.replace("'Find an address'", "'Find addresses'")}, "B: label")
    result = env.run("--check")
    assert result.returncode == 1
    assert commit_b in result.stderr
    assert env.commit_a in result.stderr


def test_hand_edited_tools_json_at_the_same_commit_fails(env):
    manifest = json.loads(env.tools.read_text())
    tool = next(t for t in manifest["tools"] if t["playground_id"] == "address-find")
    tool["tokens"]["default"] = 7
    env.tools.write_text(json.dumps(manifest, indent=2) + "\n")
    result = env.run("--check")
    assert result.returncode == 1
    assert "stale" in result.stderr


def test_catalogue_comment_edit_that_leaves_the_tools_alone_still_fails(env):
    """catalogue_sha256 is the tripwire for rules the parser does not model."""
    _commit(env.thor, {VUE_PATH: INDEX_VUE.replace("// Playground catalogue", "// The Playground catalogue")}, "B: comment")
    before = json.loads(env.tools.read_text())
    result = env.run("--check")
    assert result.returncode == 1
    assert "stale" in result.stderr
    assert json.loads(env.tools.read_text()) == before  # --check never writes


def test_tools_json_without_a_recorded_commit_fails(env):
    manifest = json.loads(env.tools.read_text())
    del manifest["source"]["commit"]
    env.tools.write_text(json.dumps(manifest, indent=2) + "\n")
    result = env.run("--check")
    assert result.returncode == 1
    assert "stale" in result.stderr


def test_reformatted_tools_json_fails(env):
    """Same data, different bytes: the comparison stays byte for byte."""
    manifest = json.loads(env.tools.read_text())
    env.tools.write_text(json.dumps(manifest, indent=4) + "\n")
    result = env.run("--check")
    assert result.returncode == 1
