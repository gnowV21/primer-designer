// VisualizationPanel — Panel 1/2/3 viewer (SPEC_visualization §E.7).
// Forwards the selected candidate + /api/design-derived fields to /api/visualize
// and renders the returned SVG. Never designs or scores. UI English.

import { useState, useEffect } from 'react';
import axios from 'axios';

const TABS = [
  ['reaction', 'Reaction'],
  ['melting', 'Melting'],
  ['gel', 'Gel'],
];

// --viz-* palette (matches backend fallbacks; also lets a future dark theme override).
const VIZ_VARS = {
  '--viz-tail': '#B07A2E', '--viz-tail-hi': '#D6A155',
  '--viz-mirna': '#2A9D8F', '--viz-mirna-hi': '#5AC7B7',
  '--viz-stemloop': '#5B6FC9', '--viz-stemloop-hi': '#8A99EA',
  '--viz-universal': '#9059C0', '--viz-universal-hi': '#B78BDC',
  '--viz-axis': '#94A3B8', '--viz-curve': '#2563EB', '--viz-derivative': '#0F766E',
  '--viz-band': '#334155', '--viz-band-ref': '#0F172A',
  '--viz-fg': '#243244', '--viz-muted': '#6B7A90', '--viz-bg': '#FFFFFF',
  '--viz-surface': '#F7F9FC', '--viz-border': '#E3E9F2', '--viz-warn': '#DC2626',
};

function triggerDownload(filename, blob) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export default function VisualizationPanel({ results, params }) {
  const top3 = results?.top3 || [];
  const [candIdx, setCandIdx] = useState(0);
  const [tab, setTab] = useState('reaction');
  const [data, setData] = useState(null);
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState(null);

  const mature = params?.sequence?.matureSequence?.trim() || '';
  const mirnaId = (results?.metadata?.mirna_id || 'miRNA').trim();
  const stemloop = results?.stemloop_rt?.sequence || '';
  const universal = results?.universal_reverse?.sequence || '';
  const cand = top3[candIdx];

  const ready = cand && mature && stemloop && universal;

  useEffect(() => {
    if (!ready) return;
    let cancelled = false;
    setStatus('loading');
    setError(null);
    const body = {
      mirna_sequence: mature,
      mirna_id: mirnaId,
      stemloop_rt: stemloop,
      forward: cand.sequence,
      forward_binding_length: cand.specific_length,
      universal_reverse: universal,
      predicted_amplicon_tm: cand.predicted_amplicon_tm ?? null,
      dimer_tm_warning: cand.dimer_tm_warning ?? null,
      panels: ['reaction', 'melting', 'gel'],
    };
    axios
      .post('/api/visualize', body, { timeout: 15000 })
      .then((r) => { if (!cancelled) { setData(r.data); setStatus('ready'); } })
      .catch((e) => {
        if (!cancelled) {
          setError(e?.response?.data?.detail || e?.message || 'Request failed');
          setStatus('error');
        }
      });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [candIdx, mature, stemloop, universal, mirnaId]);

  const svg = data?.panels?.[tab];
  const meta = data?.meta;

  function downloadSVG() {
    if (!svg) return;
    triggerDownload(`${mirnaId}_${tab}_SIMULATED.svg`, new Blob([svg], { type: 'image/svg+xml' }));
  }

  function downloadPNG() {
    if (!svg) return;
    const blob = new Blob([svg], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const img = new Image();
    img.onload = () => {
      const scale = 300 / 96; // 300 dpi
      const canvas = document.createElement('canvas');
      canvas.width = Math.round((img.width || 1000) * scale);
      canvas.height = Math.round((img.height || 600) * scale);
      const ctx = canvas.getContext('2d');
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.setTransform(scale, 0, 0, scale, 0, 0);
      ctx.drawImage(img, 0, 0);
      URL.revokeObjectURL(url);
      canvas.toBlob((b) => b && triggerDownload(`${mirnaId}_${tab}_SIMULATED_300dpi.png`, b), 'image/png');
    };
    img.onerror = () => URL.revokeObjectURL(url);
    img.src = url;
  }

  if (!ready) {
    return (
      <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500">
        Visualization needs the mature sequence and a designed primer set.
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
      {/* controls */}
      <div className="flex flex-wrap items-center gap-3 justify-between px-4 py-3 border-b border-slate-100">
        <div className="flex items-center gap-1.5">
          {TABS.map(([key, label]) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`text-xs font-semibold px-3 py-1.5 rounded-lg transition ${
                tab === key ? 'bg-teal-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          {top3.length > 1 && (
            <select
              value={candIdx}
              onChange={(e) => setCandIdx(Number(e.target.value))}
              className="text-xs border border-slate-200 rounded-lg px-2 py-1.5 text-slate-600 bg-white"
            >
              {top3.map((c, i) => (
                <option key={i} value={i}>
                  Set #{c.rank ?? i + 1}
                </option>
              ))}
            </select>
          )}
          <button
            onClick={downloadSVG}
            disabled={!svg}
            className="text-xs px-3 py-1.5 rounded-lg bg-slate-100 text-slate-600 hover:bg-slate-200 disabled:opacity-40 font-medium transition"
          >
            Download SVG
          </button>
          <button
            onClick={downloadPNG}
            disabled={!svg}
            className="text-xs px-3 py-1.5 rounded-lg bg-slate-100 text-slate-600 hover:bg-slate-200 disabled:opacity-40 font-medium transition"
          >
            PNG (300 dpi)
          </button>
        </div>
      </div>

      {/* viewport */}
      <div className="p-4 bg-slate-50/60 overflow-x-auto" style={VIZ_VARS}>
        {status === 'loading' && (
          <p className="text-sm text-slate-500 py-8 text-center">Rendering…</p>
        )}
        {status === 'error' && (
          <p className="text-sm text-red-600 py-8 text-center">Visualization failed: {error}</p>
        )}
        {status === 'ready' && svg && (
          // eslint-disable-next-line react/no-danger
          <div className="mx-auto max-w-full [&_svg]:h-auto [&_svg]:max-w-full"
               dangerouslySetInnerHTML={{ __html: svg }} />
        )}
      </div>

      {meta && (
        <p className="px-4 py-2 text-xs text-slate-500 border-t border-slate-100">
          Amplicon {meta.amplicon_length} bp · GC {meta.gc_percent}%
          {meta.dh_source === 'approximate' && ' · ΔH approximated (peak width indicative)'}
          {' · Simulated from predicted values — not experimental data'}
        </p>
      )}
      {/* Amplicon Tm depends strongly on Mg2+ (audit SCI-07) — show the span, not one number. */}
      {tab === 'melting' && cand?.predicted_amplicon_tm_mg_span && (
        <p className="px-4 pb-2 text-xs text-slate-500">
          Predicted melt peak {cand.predicted_amplicon_tm} °C at your Mg²⁺ setting ·{' '}
          {cand.predicted_amplicon_tm_mg_span.tm_c[0]}–{cand.predicted_amplicon_tm_mg_span.tm_c[1]} °C
          across {cand.predicted_amplicon_tm_mg_span.mg_mM[0]}–{cand.predicted_amplicon_tm_mg_span.mg_mM[1]} mM Mg²⁺.
          Empirical formula — compare with your instrument&apos;s melt peak rather than expecting an exact match.
        </p>
      )}
    </div>
  );
}
