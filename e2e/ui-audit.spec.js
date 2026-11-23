// E2E — UI audit (UI/PDF review 2026-11-23, docs/REVIEW_ui_polish_2026-11.md).
//
// Every main page at 1366 px and 375 px, with its content opened up (parameter groups,
// result panels, an Analyzer example run, a miR-16 design):
//   1. every text element reaches WCAG AA contrast (4.5:1; 3:1 for ≥ 24 px or ≥ 18.66 px bold),
//      disabled controls included,
//   2. the page never scrolls sideways,
//   3. no primer/miRNA sequence and no miRNA name is split across two lines,
//   4. chart text (SVG) is at least 11 px on screen.
// A failure lists the offending elements, so the report says what to fix.

import { test, expect } from '@playwright/test';

const MIR16 = { name: 'hsa-miR-16-5p', sequence: 'UAGCAGCACGUAAAUAUUGGCG' };
const WIDTHS = [1366, 375];

/** Runs in the page: collect contrast, overflow, split-sequence and SVG font problems. */
function audit() {
  const parse = (s) => {
    const m = s.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(/[\s,/]+/).filter(Boolean).map(Number);
    return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1];
  };
  const blend = (fg, bg) => [0, 1, 2].map((i) => fg[i] * fg[3] + bg[i] * (1 - fg[3])).concat(1);
  const lum = (c) => {
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]);
  };
  const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
  const bgOf = (el) => {
    const layers = [];
    for (let e = el; e; e = e.parentElement) {
      const cs = getComputedStyle(e);
      if (cs.backgroundImage && cs.backgroundImage !== 'none' && !cs.backgroundImage.startsWith('url')) return null;
      const c = parse(cs.backgroundColor);
      if (c && c[3] > 0) { layers.push(c); if (c[3] >= 1) break; }
    }
    let bg = [255, 255, 255, 1];
    for (const c of layers.reverse()) bg = blend(c, bg);
    return bg;
  };
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return false;
    for (let e = el; e; e = e.parentElement) {
      const cs = getComputedStyle(e);
      if (cs.visibility === 'hidden' || cs.display === 'none' || Number(cs.opacity) === 0) return false;
    }
    return true;
  };
  const label = (el) => `${el.tagName.toLowerCase()}${el.id ? '#' + el.id : ''}${el.dataset.testid ? `[${el.dataset.testid}]` : ''}`;

  const contrast = [];
  for (const el of document.body.querySelectorAll('*')) {
    if (el.closest('svg, script, style, noscript')) continue;
    const own = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
    if (!own || !visible(el)) continue;
    const cs = getComputedStyle(el);
    const bg = bgOf(el);
    const fg = parse(cs.color);
    if (!bg || !fg) continue;
    const r = ratio(blend(fg, bg), bg);
    const size = parseFloat(cs.fontSize);
    const bold = Number(cs.fontWeight) >= 700;
    const need = size >= 24 || (size >= 18.66 && bold) ? 3 : 4.5;
    if (r < need - 0.01) {
      contrast.push({ el: label(el), text: el.textContent.trim().slice(0, 50), ratio: +r.toFixed(2),
        color: cs.color, bg: `rgb(${bg.slice(0, 3).map(Math.round).join(',')})`, size });
    }
  }

  const main = document.querySelector('main');
  const overflow = Math.max(
    document.documentElement.scrollWidth - document.documentElement.clientWidth,
    main ? main.scrollWidth - main.clientWidth : 0,
  );

  // Sequences (≥ 12 nt) and miRNA names must stay on one line.
  const rx = /[ACGTU]{12,}|\b(?:[a-z]{3,5}-)?(?:miR|let)-\d+[a-z]?(?:-\d+)?(?:-[35]p)?\b/g;
  const split = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const host = n.parentElement;
    if (!host || host.closest('svg, script, style, textarea, option') || !visible(host)) continue;
    for (const m of n.textContent.matchAll(rx)) {
      const range = document.createRange();
      range.setStart(n, m.index);
      range.setEnd(n, m.index + m[0].length);
      const tops = new Set([...range.getClientRects()].filter((q) => q.width > 0).map((q) => Math.round(q.top)));
      if (tops.size > 1) split.push({ text: m[0], el: label(host), context: n.textContent.trim().slice(0, 60) });
    }
  }

  // Chart text drawn smaller than 11 px on screen.
  const svgSmall = [];
  for (const t of document.querySelectorAll('svg text')) {
    if (!visible(t) || !t.textContent.trim()) continue;
    const h = t.getBoundingClientRect().height;
    const px = parseFloat(getComputedStyle(t).fontSize);
    const svg = t.ownerSVGElement;
    const scale = svg && svg.viewBox?.baseVal?.width ? svg.getBoundingClientRect().width / svg.viewBox.baseVal.width : 1;
    const shown = px * scale;
    if (shown < 10.5 && h > 0) svgSmall.push({ text: t.textContent.trim().slice(0, 30), px: +shown.toFixed(1) });
  }
  return { contrast, overflow, split, svgSmall };
}

async function openAll(page, scope = 'main') {
  for (let round = 0; round < 4; round++) {
    const n = await page.evaluate((sel) => {
      const root = document.querySelector(sel) || document.body;
      const closed = [...root.querySelectorAll('button[aria-expanded="false"]')]
        .filter((b) => b.offsetParent !== null && !/re-run|adjust/i.test(b.textContent));
      closed.forEach((b) => b.click());
      return closed.length;
    }, scope);
    if (!n) break;
    await page.waitForTimeout(300);
  }
}

async function designMir16(page) {
  await page.goto('/design');
  await page.getByLabel(/miRNA name, accession or sequence/i).fill(MIR16.sequence);
  await page.getByRole('button', { name: /^Search$/ }).click();
  const btn = page.getByRole('button', { name: /^Design primers$/ });
  await expect(btn).toBeEnabled({ timeout: 10_000 });
  await btn.click();
  await expect(page).toHaveURL('/results', { timeout: 60_000 });
  await expect(page.getByTestId('set-comparison')).toBeVisible({ timeout: 60_000 });
}

const PAGES = [
  { path: '/home', prep: async (page) => { await page.goto('/home'); } },
  { path: '/design', prep: async (page) => {
    await page.goto('/design');
    await page.getByRole('button', { name: /Parameters/ }).first().click();
    await openAll(page);
  } },
  { path: '/results', prep: async (page) => { await designMir16(page); await openAll(page); } },
  { path: '/analyze', prep: async (page) => {
    await page.goto('/analyze');
    await page.getByRole('button', { name: /Load example/i }).click();
    await page.getByRole('button', { name: /^Analyze primers$/ }).click();
    await expect(page.getByTestId('analyze-results')).toBeVisible({ timeout: 30_000 });
  } },
  { path: '/history', prep: async (page) => { await designMir16(page); await page.goto('/history'); } },
  { path: '/benchmark', prep: async (page) => {
    await page.goto('/benchmark');
    await page.waitForLoadState('networkidle');
  } },
];

for (const width of WIDTHS) {
  for (const pg of PAGES) {
    test(`audit ${pg.path} at ${width} px`, async ({ page }, info) => {
      test.setTimeout(150_000);
      await page.setViewportSize({ width, height: 900 });
      await pg.prep(page);
      await page.waitForTimeout(400);
      const r = await page.evaluate(audit);
      await info.attach('audit.json', { body: JSON.stringify(r, null, 2), contentType: 'application/json' });
      if (r.contrast.length || r.split.length || r.overflow || r.svgSmall.length) {
        console.log(`[audit ${pg.path} ${width}px] overflow ${r.overflow}px; contrast ${r.contrast.length}; `
          + `split ${r.split.length}; svg<11px ${r.svgSmall.length}\n`
          + JSON.stringify({ contrast: r.contrast.slice(0, 12), split: r.split.slice(0, 8),
            svgSmall: r.svgSmall.slice(0, 6) }, null, 1));
      }
      expect.soft(r.overflow, 'horizontal page overflow (px)').toBe(0);
      expect.soft(r.contrast, 'text below WCAG AA contrast').toEqual([]);
      expect.soft(r.split, 'sequence or miRNA name split across lines').toEqual([]);
      expect.soft(r.svgSmall, 'chart text below 11 px').toEqual([]);
    });
  }
}
