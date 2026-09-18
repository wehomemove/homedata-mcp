#!/usr/bin/env node
/**
 * generate-manifest: builds homedata_mcp/manifest/tools.json from the Developer
 * Playground catalogue in thor, the source of truth for which endpoints the MCP
 * offers (every callable endpoint that is not enterprise, exactly as the
 * Playground offers it).
 *
 *   node scripts/generate-manifest.mjs --thor <path to a thor clone> [--ref origin/main]
 *   node scripts/generate-manifest.mjs --thor <path> --check    exit 1 if tools.json is stale
 *   node scripts/generate-manifest.mjs --thor <path> --init-descriptions
 *
 * WHY LOCAL: thor is a private repository and this package is public, so CI
 * cannot read the catalogue. The manifest is generated here at a stated thor
 * commit and committed. The automated drift signal is scripts/check_drift.py,
 * which reads the public https://homedata.co.uk/llms-full.txt that thor
 * generates from the same catalogue.
 *
 * WHAT IT READS (via `git show <ref>:<path>`, so no checkout is touched)
 *   resources/js/Pages/Developer/Playground/Index.vue
 *     ENDPOINTS, ENDPOINT_WEIGHTS, ENDPOINT_CREDIT_PENCE, NUMERIC_PARAM_NAMES, PROPERTY_ADDONS
 *     estimatedCallCost()   cost rules that live in code, not in the weight map
 *     resolveEndpointPath() path rules that live in code
 *   public/llms-full.txt    the api-surface source_hash, recorded as provenance
 *
 * FAILS LOUDLY when the catalogue grows a cost or path rule this script does
 * not know. A new `ep.id === '…'` branch in estimatedCallCost would otherwise be
 * silently published at its map weight.
 */
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { existsSync, readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const OUT_DIR = join(ROOT, 'homedata_mcp/manifest');
const TOOLS_OUT = join(OUT_DIR, 'tools.json');
const DESCRIPTIONS_OUT = join(OUT_DIR, 'descriptions.json');
const CONFIG = JSON.parse(readFileSync(join(ROOT, 'scripts/manifest-config.json'), 'utf8'));

const VUE_PATH = 'resources/js/Pages/Developer/Playground/Index.vue';
const LLMS_PATH = 'public/llms-full.txt';

const argv = process.argv.slice(2);
const arg = (name) => { const i = argv.indexOf(name); return i === -1 ? null : argv[i + 1]; };
const THOR = arg('--thor') || die('--thor <path to a thor clone> is required');
const REF = arg('--ref') || 'origin/main';
const CHECK = argv.includes('--check');
const INIT_DESCRIPTIONS = argv.includes('--init-descriptions');

function die(msg) { console.error(`generate-manifest: ${msg}`); process.exit(2); }
const git = (...args) => execFileSync('git', ['-C', THOR, ...args], { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });

const commit = git('rev-parse', `${REF}^{commit}`).trim();
const vue = git('show', `${commit}:${VUE_PATH}`);
const llms = git('show', `${commit}:${LLMS_PATH}`);

// ── Block extraction ────────────────────────────────────────────────────────
// Same algorithm as thor's scripts/sync-try-catalogue.mjs extractBlock(): find
// `const NAME = [` / `{` / `new Set(` at line start and return the text through
// its matching closer, skipping brackets inside strings and comments.
function extractBlock(src, name) {
    const re = new RegExp('^const ' + name + ' = (\\[|\\{|new Set\\()', 'm');
    const m = re.exec(src);
    if (!m) die(`block ${name} not found in ${VUE_PATH}`);
    return balanced(src, m.index, m.index + m[0].length - 1);
}

// Returns src[start .. matching closer of the opener at `openAt`].
function balanced(src, start, openAt) {
    let i = openAt;
    const opener = src[i];
    const closer = { '[': ']', '{': '}', '(': ')' }[opener];
    let depth = 0;
    while (i < src.length) {
        const c = src[i];
        if (c === '/' && src[i + 1] === '/') { i = src.indexOf('\n', i); if (i === -1) break; continue; }
        if (c === '/' && src[i + 1] === '*') { i = src.indexOf('*/', i) + 2; continue; }
        if (c === "'" || c === '"' || c === '`') {
            const q = c; i++;
            while (i < src.length && src[i] !== q) { if (src[i] === '\\') i++; i++; }
            i++; continue;
        }
        if (c === opener) depth++;
        else if (c === closer) { depth--; if (depth === 0) return src.slice(start, i + 1); }
        i++;
    }
    die(`unbalanced block starting at offset ${start}`);
}

// Body of `const NAME = computed(() => {…})` or `const NAME = (…) => {…}`.
function functionBody(src, name) {
    const at = src.search(new RegExp('^const ' + name + ' = ', 'm'));
    if (at === -1) die(`function ${name} not found in ${VUE_PATH}`);
    const brace = src.indexOf('{', src.indexOf('=>', at));
    return balanced(src, brace, brace);
}

const data = new Function(`
    ${['ENDPOINTS', 'ENDPOINT_WEIGHTS', 'ENDPOINT_CREDIT_PENCE', 'NUMERIC_PARAM_NAMES', 'PROPERTY_ADDONS'].map((n) => extractBlock(vue, n)).join(';\n')};
    return { ENDPOINTS, ENDPOINT_WEIGHTS, ENDPOINT_CREDIT_PENCE, NUMERIC_PARAM_NAMES, PROPERTY_ADDONS };
`)();

// ── Code rules: refuse anything unrecognised ────────────────────────────────
const costBody = functionBody(vue, 'estimatedCallCost');
const costBranches = [...costBody.matchAll(/ep\.id === '([^']+)'/g)].map((m) => m[1]).sort();
const knownCostBranches = Object.keys(CONFIG.cost_rules).sort();
if (JSON.stringify(costBranches) !== JSON.stringify(knownCostBranches)) {
    die(`estimatedCallCost branches are [${costBranches}] but manifest-config.json cost_rules knows [${knownCostBranches}]. `
        + 'Read the new branch in Index.vue and encode it before regenerating.');
}
for (const [id, rule] of Object.entries(CONFIG.cost_rules)) {
    if (!rule.source_pattern) continue;
    const m = costBody.match(new RegExp(rule.source_pattern));
    if (!m) die(`cost rule for ${id} no longer matches Index.vue (pattern ${rule.source_pattern})`);
    for (const [k, group] of Object.entries(rule.captures ?? {})) rule[k] = Number(m[group]);
}

const pathBody = functionBody(vue, 'resolveEndpointPath');
const pathBranches = [...pathBody.matchAll(/ep\.id !== '([^']+)'/g)].map((m) => m[1]);
if (JSON.stringify(pathBranches) !== JSON.stringify(['risks'])) {
    die(`resolveEndpointPath special-cases [${pathBranches}]; this script only knows risks' flood:<layer> rule`);
}

const surfaceHash = llms.match(/BEGIN GENERATED: api-surface \(source_hash: ([0-9a-f]{64})\)/)?.[1]
    ?? die(`${LLMS_PATH} has no api-surface source_hash at ${commit}`);

// ── Build ───────────────────────────────────────────────────────────────────
const toolName = (id) => id.replace(/-/g, '_');
const templ = (path) => path.replace(/:(\w+)/g, '{$1}');
const DIGITS = data.NUMERIC_PARAM_NAMES; // the Playground strips non-digits from these

function param(p) {
    const values = p.options ? p.options.map((o) => o.value ?? o)
        : p.optionGroups ? p.optionGroups.flatMap((g) => g.options.map((o) => o.value)) : null;
    const out = {
        name: p.name,
        in: p.inPath ? 'path' : 'query',
        type: p.type === 'number' ? 'number' : 'string',
        required: Boolean(p.required),
    };
    if (values) out.enum = values.map(String);
    if (!values && out.type === 'string' && DIGITS.has(p.name)) out.pattern = '^\\d+$';
    if (p.orWithPrevious) out.alternative_to_previous = true;
    if (p.pairedWith) out.paired_with = p.pairedWith;
    if (p.advanced) out.advanced = true;
    if (p.hint) out.playground_hint = p.hint;
    return out;
}

function tokens(e) {
    const rule = CONFIG.cost_rules[e.id];
    const w = data.ENDPOINT_WEIGHTS[e.id];
    if (!rule) {
        if (w === undefined) die(`${e.id} has no ENDPOINT_WEIGHTS entry and no cost rule`);
        return { default: w };
    }
    if (rule.kind === 'plus_addons') {
        // The builder offers PROPERTY_ADDONS minus comingSoon; each adds its own cost to the base.
        const addons = Object.fromEntries(data.PROPERTY_ADDONS.filter((a) => !a.comingSoon).map((a) => [a.id, a.cost]));
        return { default: rule.base, plus_with_addons: true, addons };
    }
    if (rule.kind === 'when_param') {
        return { default: rule.default ?? w, when: [{ param: rule.param, in: rule.values, tokens: rule.tokens }] };
    }
    die(`unknown cost rule kind ${rule.kind} for ${e.id}`);
}

const tools = [];
const excluded = [];
for (const e of data.ENDPOINTS) {
    let reason = null;
    if (!e.path) reason = 'no_path';
    else if (e.enterprise) reason = 'enterprise';
    else if (e.adminOnly && !CONFIG.include_admin_only.includes(e.id)) reason = 'admin_only';
    if (reason) {
        excluded.push({ playground_id: e.id, reason, ...(CONFIG.exclusion_notes[e.id] ? { note: CONFIG.exclusion_notes[e.id] } : {}) });
        continue;
    }
    if (data.ENDPOINT_CREDIT_PENCE[e.id] != null) die(`${e.id} is billed in reveal credits; the manifest has no credit model`);
    const params = (e.params ?? []).map(param).concat(CONFIG.param_additions[e.id] ?? []);
    const tool = {
        name: toolName(e.id),
        playground_id: e.id,
        label: e.label,
        method: e.method,
        path: templ(e.path),
        params,
        tokens: tokens(e),
    };
    const flood = params.find((p) => p.name === 'risk_type')?.enum?.filter((v) => v.startsWith('flood:'));
    if (e.id === 'risks' && flood?.length) {
        tool.path_rules = [{ param: 'risk_type', prefix: 'flood:', path: '/risks/flood/{suffix}/' }];
    }
    tools.push(tool);
}

const names = tools.map((t) => t.name).concat(CONFIG.static_tools.map((t) => t.name));
const dupes = names.filter((n, i) => names.indexOf(n) !== i);
if (dupes.length) die(`duplicate tool names: ${dupes}`);
const bad = names.filter((n) => !/^[a-zA-Z0-9_-]{1,64}$/.test(n));
if (bad.length) die(`tool names outside the MCP name grammar: ${bad}`);

const manifest = {
    schema_version: 1,
    source: {
        repository: 'wehomemove/thor',
        commit,
        catalogue: VUE_PATH,
        catalogue_sha256: createHash('sha256').update(vue).digest('hex'),
        llms_full_api_surface_source_hash: surfaceHash,
    },
    rules: {
        offered: 'Playground ENDPOINTS entries with a path, not enterprise:true, not adminOnly:true',
        tool_name: 'snake_case of the Playground id (hyphens become underscores). A design choice: the Playground has ids and labels, no tool names.',
        base_url: 'Paths are relative to https://api.homedata.co.uk and also answer under /api/.',
    },
    tools,
    static_tools: CONFIG.static_tools,
    excluded,
};

const text = JSON.stringify(manifest, null, 2) + '\n';
if (CHECK) {
    const current = existsSync(TOOLS_OUT) ? readFileSync(TOOLS_OUT, 'utf8') : '';
    if (current !== text) { console.error(`tools.json is stale against thor ${commit}; regenerate`); process.exit(1); }
    console.log(`tools.json is current against thor ${commit}`);
    process.exit(0);
}
mkdirSync(OUT_DIR, { recursive: true });
writeFileSync(TOOLS_OUT, text);

const reasons = excluded.reduce((acc, x) => ({ ...acc, [x.reason]: (acc[x.reason] ?? 0) + 1 }), {});
console.log(`thor ${commit}: ${tools.length} tools, ${CONFIG.static_tools.length} static tools, ${excluded.length} excluded ${JSON.stringify(reasons)}`);

// ── Descriptions overlay: stub what is missing, never overwrite ─────────────
if (INIT_DESCRIPTIONS) {
    const overlay = existsSync(DESCRIPTIONS_OUT) ? JSON.parse(readFileSync(DESCRIPTIONS_OUT, 'utf8')) : {};
    const phrase = (t) => {
        const n = (x) => `${x} token${x === 1 ? '' : 's'}`;
        if (t.plus_with_addons) return `Costs ${n(t.default)} plus the price of each add-on requested.`;
        if (t.default === 0) return 'Free: no tokens spent.';
        if (t.when) return `Costs ${n(t.default)}; ${t.when.map((w) => `${n(w.tokens)} when ${w.param} is ${w.in.join(' or ')}`).join('; ')}.`;
        return `Costs ${n(t.default)}.`;
    };
    let added = 0;
    for (const t of tools) if (!overlay[t.name]) { overlay[t.name] = `${t.label}. ${phrase(t.tokens)}`; added++; }
    for (const t of CONFIG.static_tools) if (!overlay[t.name]) { overlay[t.name] = t.stub_description; added++; }
    const sorted = Object.fromEntries(Object.keys(overlay).sort().map((k) => [k, overlay[k]]));
    writeFileSync(DESCRIPTIONS_OUT, JSON.stringify(sorted, null, 2) + '\n');
    console.log(`descriptions.json: ${added} stubs added, ${Object.keys(sorted).length} total`);
}
