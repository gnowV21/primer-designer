// check_tier_order.mjs — the frontend tier comparator vs the API order
// (docs/SPEC_ui_tiered_4.0.0.md §3, "Đối chiếu dữ liệu thật").
//
// Reads outputs/freeze_cache/ui_top3_hsa.jsonl.gz (backend/scripts/ui_top3_dump.py),
// sorts each design's top 3 with compareTiered from src/utils/tierRank.js and checks
// that the order equals the API's. Also tallies which key step decides #1 vs #2 and
// how many returned pairs are "Equivalent in silico". Node built-ins only.
//
// Usage (repo root): node frontend/scripts/check_tier_order.mjs [path] [--json out.json]
import { readFileSync, writeFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { compareTiered, decidingStep, equivalentInSilico, hasTiers, KEY_STEPS, tierReason }
  from '../src/utils/tierRank.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const jsonOut = args.includes('--json') ? args[args.indexOf('--json') + 1] : null;
const file = args.find((a, i) => !a.startsWith('--') && args[i - 1] !== '--json')
  ?? path.join(here, '..', '..', 'outputs', 'freeze_cache', 'ui_top3_hsa.jsonl.gz');

const lines = gunzipSync(readFileSync(file)).toString('utf8').split('\n').filter(Boolean);
let designs = 0, same = 0, single = 0, notTiered = 0;
const mismatches = [];
const step12 = Object.fromEntries([...KEY_STEPS, 'identical'].map((k) => [k, 0]));
const reasonStep = {};
let equivalentPairs = 0;

for (const line of lines) {
  const rec = JSON.parse(line);
  const top = rec.top3 || [];
  if (!top.length) continue;
  designs += 1;
  if (!top.every(hasTiers)) { notTiered += 1; continue; }
  const sorted = [...top].sort(compareTiered);
  const ok = sorted.every((s, i) => s.sequence === top[i].sequence);
  if (ok) same += 1;
  else mismatches.push({ mirna: rec.mirna, api: top.map((s) => s.sequence), frontend: sorted.map((s) => s.sequence) });
  if (top.length < 2) { single += 1; continue; }
  const st = decidingStep(top[0], top[1]);
  step12[st === -1 ? 'identical' : KEY_STEPS[st]] += 1;
  const rs = tierReason(top[0], top[1]).step;
  reasonStep[rs] = (reasonStep[rs] || 0) + 1;
  for (let i = 0; i < top.length; i++) {
    for (let j = i + 1; j < top.length; j++) if (equivalentInSilico(top[i], top[j])) equivalentPairs += 1;
  }
}

const summary = {
  source: path.relative(path.join(here, '..', '..'), file).replaceAll('\\', '/'),
  designs_with_sets: designs,
  order_identical: same,
  order_different: mismatches.length,
  not_tiered: notTiered,
  designs_with_one_set: single,
  deciding_step_1_vs_2: step12,
  rank_reason_branch_1_vs_2: reasonStep,
  equivalent_in_silico_pairs: equivalentPairs,
  mismatches: mismatches.slice(0, 20),
};
console.log(JSON.stringify(summary, null, 1));
if (jsonOut) writeFileSync(jsonOut, JSON.stringify(summary, null, 1) + '\n');
process.exit(mismatches.length || notTiered ? 1 : 0);
