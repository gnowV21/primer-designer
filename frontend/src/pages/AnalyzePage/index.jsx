import { useState, useEffect } from 'react';
import axios from 'axios';
import { DEFAULTS } from '../../constants/defaults.js';
import OffTargetPanel from '../SearchPage/ResultsSection/OffTargetPanel.jsx';
import LnaPanel from '../../components/LnaPanel/index.jsx';
import MiRNASearchInput from '../../components/MiRNASearchInput.jsx';
import useLnaEnabled from '../../hooks/useLnaEnabled.js';
import useDraftState from '../../hooks/useDraftState.js';

const UNIVERSAL_REVERSE = 'CCAGTGCAGGGTCCGAGGTA';

// A worked example (hsa-miR-21-5p) so users can see the page produce output
// immediately — RT/forward derived exactly as the design pipeline would.
const EXAMPLE = {
  mirnaId: 'hsa-miR-21-5p',
  mature:  'UAGCUUAUCAGACUGAUGUUGA',
  rt:      'GTCGTATCCAGTGCAGGGTCCGAGGTATTCGCACTGGATACGACTCAACA',
  forward: 'GCGGCGTAGCTTATCAGACTGA',
  reverse: UNIVERSAL_REVERSE,
};

const ION_DEFAULTS = {
  saltConcentration:      DEFAULTS.thermodynamic.saltConcentration,
  kPlusConc:              DEFAULTS.thermodynamic.kPlusConc,
  magnesiumConcentration: DEFAULTS.thermodynamic.magnesiumConcentration,
  dntpTotal:              DEFAULTS.thermodynamic.dntpTotal,
  primerConcentration:    DEFAULTS.thermodynamic.primerConcentration,
  bufferPH:               DEFAULTS.thermodynamic.bufferPH,
  annealingTemp:          DEFAULTS.qpcr.annealingTemp,
};

const ION_FIELDS = [
  { key: 'saltConcentration',      label: 'Na⁺',        unit: 'mM', step: 1 },
  { key: 'kPlusConc',              label: 'K⁺',         unit: 'mM', step: 1 },
  { key: 'magnesiumConcentration', label: 'Mg²⁺',      unit: 'mM', step: 0.1 },
  { key: 'dntpTotal',              label: 'dNTP total', unit: 'mM', step: 0.1 },
  { key: 'primerConcentration',    label: 'Primer',     unit: 'nM', step: 10 },
  { key: 'bufferPH',               label: 'Buffer pH',  unit: '',   step: 0.1 },
  { key: 'annealingTemp',          label: 'Annealing',  unit: '°C', step: 1 },
];

export default function AnalyzePage() {
  // Draft persistence: inputs survive navigating away (e.g. to /search) and are
  // restored on return. A full reload clears them (see useDraftState).
  const [rt, setRt]           = useDraftState('analyzeDraft.rt', '');
  const [forward, setForward] = useDraftState('analyzeDraft.forward', '');
  const [reverse, setReverse] = useDraftState('analyzeDraft.reverse', UNIVERSAL_REVERSE);
  const [mature, setMature]   = useDraftState('analyzeDraft.mature', '');
  const [mirnaId, setMirnaId] = useDraftState('analyzeDraft.mirnaId', '');
  const [params, setParams]   = useDraftState('analyzeDraft.params', ION_DEFAULTS);
  const [showParams, setShowParams] = useDraftState('analyzeDraft.showParams', false);

  // Results are ephemeral — re-run with one click after returning.
  const [status, setStatus] = useState('idle'); // idle | loading | done | error
  const [result, setResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [showLna, setShowLna] = useState(false);
  const lnaEnabled = useLnaEnabled();

  useEffect(() => { document.title = 'HG Lab | Primer Analyzer'; }, []);

  function loadExample() {
    setMirnaId(EXAMPLE.mirnaId);
    setMature(EXAMPLE.mature);
    setRt(EXAMPLE.rt);
    setForward(EXAMPLE.forward);
    setReverse(EXAMPLE.reverse);
    setStatus('idle');
    setResult(null);
    setErrorMsg('');
  }

  function clearAll() {
    setMirnaId(''); setMature(''); setRt(''); setForward('');
    setReverse(UNIVERSAL_REVERSE);
    setStatus('idle'); setResult(null); setErrorMsg(''); setShowLna(false);
  }

  async function analyze() {
    setStatus('loading');
    setResult(null);
    setErrorMsg('');
    setShowLna(false);
    try {
      const { data } = await axios.post('/api/analyze', {
        primers: { rt, forward, reverse },
        matureSequence: mature,
        mirnaId,
        params,
      });
      setResult(data);
      setStatus('done');
    } catch (err) {
      setErrorMsg(err.response?.data?.error || err.message || 'Analysis failed.');
      setStatus('error');
    }
  }

  const canSubmit = rt.trim() && forward.trim() && reverse.trim() && mature.trim() && status !== 'loading';

  // Sanitise the miRNA id for BLAST (backend requires -5p/-3p arm, else 400).
  const blastMirnaId = /-(5p|3p)$/i.test(mirnaId.trim()) ? mirnaId.trim() : '';

  return (
    <div className="max-w-4xl mx-auto space-y-6">

      {/* Header */}
      <div className="space-y-1">
        <h1 className="text-xl font-bold text-slate-800">Primer Analyzer</h1>
        <p className="text-sm text-slate-500 leading-relaxed">
          Already have a stem-loop RT-qPCR primer set? Paste the three primers and the mature
          miRNA — this computes their thermodynamic parameters, cross-dimer risk, and checks each
          primer against the miRNA it targets. No design is run; your sequences are analysed as-is.
        </p>
      </div>

      {/* ── Input card ── */}
      <div className="rounded-2xl border border-slate-200 bg-white shadow-sm p-6 space-y-5">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-600">Input</h2>
          <div className="flex items-center gap-3 text-xs">
            <button onClick={loadExample} className="text-teal-600 hover:underline font-medium">Load example</button>
            <span className="text-slate-300">·</span>
            <button onClick={clearAll} className="text-slate-400 hover:text-slate-600">Clear</button>
          </div>
        </div>

        {/* miRNA — unified search (name / miRBase ID / sequence) with autocomplete */}
        <div className="space-y-2">
          <div>
            <span className="text-xs font-medium text-slate-600">Mature miRNA</span>
            <span className="text-xs text-slate-400 ml-1">· type a name/ID for suggestions, or paste the RNA sequence (A/U/G/C)</span>
          </div>
          <MiRNASearchInput
            initialQuery={mirnaId || mature}
            onResolve={(r) => { setMature((r.sequence || '').toUpperCase()); setMirnaId(r.id || ''); }}
            onRawSequence={(seq) => { setMature(seq); setMirnaId(''); }}
            onClear={() => { setMature(''); setMirnaId(''); }}
          />

          {mature && (
            <div className="border border-teal-200 rounded-xl bg-teal-50/40 px-4 py-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-sm">
              <span className="text-xs text-slate-400 uppercase tracking-wide">miRNA</span>
              <span className="font-mono font-semibold text-slate-800">{mirnaId || '—'}</span>
              <SeqWithSeed seq={mature} />
              <span className="text-xs bg-white border border-teal-200 text-teal-700 rounded px-2 py-0.5 tabular-nums">{mature.length} nt</span>
            </div>
          )}
        </div>

        {/* 3 primers */}
        <div className="space-y-4">
          <PrimerInput
            label="Stem-loop RT primer" accent="border-l-teal-400"
            value={rt} onChange={setRt}
            placeholder="GTCGTATCCAGTGCAGGGTCCGAGGTA…TCAACA"
            hint="Hairpin body + 3' overhang (6 nt) complementary to the miRNA 3' end"
          />
          <PrimerInput
            label="Forward qPCR primer" accent="border-l-teal-400"
            value={forward} onChange={setForward}
            placeholder="GCGGCGTAGCTTATCAGACTGA"
            hint="Synthetic 5' tail + miRNA-specific 5' region"
          />
          <PrimerInput
            label="Universal reverse primer" accent="border-l-slate-300"
            value={reverse} onChange={setReverse}
            placeholder={UNIVERSAL_REVERSE}
            hint="Fixed across all assays — pre-filled with the canonical sequence"
          />
        </div>

        {/* Ion conditions (collapsible) */}
        <div>
          <button
            onClick={() => setShowParams((v) => !v)}
            className="text-xs font-medium text-slate-500 hover:text-slate-700 flex items-center gap-1"
          >
            <span className={`transition-transform ${showParams ? 'rotate-90' : ''}`}>▸</span>
            Reaction conditions {showParams ? '' : '(defaults: 50 mM Na⁺, 50 mM K⁺, 1.5 mM Mg²⁺, 0.8 mM dNTP, 200 nM primer, pH 8.4, 60 °C)'}
          </button>
          {showParams && (
            <div className="mt-3 grid grid-cols-2 md:grid-cols-5 gap-3">
              {ION_FIELDS.map(({ key, label, unit, step }) => (
                <label key={key} className="block space-y-1">
                  <span className="text-xs text-slate-500">{label} <span className="text-slate-400">({unit})</span></span>
                  <input
                    type="number" step={step} value={params[key]}
                    onChange={(e) => setParams((p) => ({ ...p, [key]: parseFloat(e.target.value) }))}
                    className="w-full text-sm px-2 py-1.5 rounded-lg border border-slate-200 focus:border-teal-400 outline-none tabular-nums"
                  />
                </label>
              ))}
            </div>
          )}
        </div>

        {/* Submit */}
        <div className="flex items-center gap-3 pt-1">
          <button
            onClick={analyze}
            disabled={!canSubmit}
            className="px-6 py-2.5 bg-gradient-to-r from-teal-600 to-teal-800 text-white text-sm font-medium rounded-xl shadow-sm hover:opacity-90 transition-all active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {status === 'loading' ? 'Analyzing…' : 'Analyze primers'}
          </button>
          {status === 'error' && (
            <p className="text-sm text-red-700">{errorMsg}</p>
          )}
        </div>
      </div>

      {/* ── Results ── */}
      {status === 'done' && result && (
        <div className="space-y-6">

          {/* Per-primer metrics */}
          <section className="space-y-3">
            <h2 className="text-sm font-semibold text-slate-600">Per-primer parameters</h2>
            <div className="grid grid-cols-1 gap-3">
              <PrimerCard title="Stem-loop RT primer"      data={result.primers.rt} />
              <PrimerCard title="Forward qPCR primer"       data={result.primers.forward} />
              <PrimerCard title="Universal reverse primer"  data={result.primers.reverse} />
            </div>
          </section>

          {/* Cross-dimer matrix */}
          <section className="space-y-3">
            <h2 className="text-sm font-semibold text-slate-600">Cross-dimer matrix</h2>
            <div className="rounded-xl border border-slate-200 overflow-hidden bg-white">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 border-b border-slate-200 text-xs text-slate-500">
                  <tr>
                    <th className="text-left px-4 py-2 font-semibold">Pair</th>
                    <th className="text-right px-4 py-2 font-semibold">ΔG overall</th>
                    <th className="text-right px-4 py-2 font-semibold">ΔG 3′-end</th>
                    <th className="text-center px-4 py-2 font-semibold">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {result.cross_dimers.map((d) => {
                    const s = dimerStatus(d);
                    return (
                      <tr key={d.pair} title={d.note}>
                        <td className="px-4 py-2.5 font-medium text-slate-700">{d.pair}</td>
                        <td className="px-4 py-2.5 text-right font-mono tabular-nums text-slate-600">{fmt(d.dg_overall)}</td>
                        <td className="px-4 py-2.5 text-right font-mono tabular-nums text-slate-600">{fmt(d.dg_3prime)}</td>
                        <td className="px-4 py-2.5 text-center">
                          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${s.cls}`}>{s.label}</span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <p className="text-xs text-slate-400">ΔG in kcal/mol. More negative = more stable dimer. A stable 3′-end dimer is the concern — the polymerase can extend it into primer-dimer artifacts.</p>
          </section>

          {/* Context vs miRNA */}
          {result.context?.provided && (
            <section className="space-y-3">
              <h2 className="text-sm font-semibold text-slate-600">Consistency with the mature miRNA</h2>
              <div className="grid grid-cols-1 gap-3">
                <ContextRow
                  title="RT 3′ overhang binding"
                  ok={result.context.rt_overhang.matches}
                  note={result.context.rt_overhang.note}
                  extra={
                    <div className="flex flex-wrap gap-2 mt-1">
                      <Kv k="expected" v={result.context.rt_overhang.expected} mono />
                      <Kv k="observed" v={result.context.rt_overhang.observed} mono />
                      {result.context.rt_overhang.hybrid_tm_c != null && (
                        <Kv k="hybrid Tm" v={`${result.context.rt_overhang.hybrid_tm_c} °C`} />
                      )}
                    </div>
                  }
                />
                <ContextRow
                  title="Forward specific region"
                  ok={result.context.forward_anchor.within_expected}
                  note={result.context.forward_anchor.note}
                  extra={
                    <div className="flex flex-wrap gap-2 mt-1">
                      <Kv k="matched" v={`${result.context.forward_anchor.matched_len} nt`} />
                      <Kv k="tail ≈" v={`${result.context.forward_anchor.tail_len} nt`} />
                      {result.context.forward_anchor.matched_seq && (
                        <Kv k="on miRNA" v={result.context.forward_anchor.matched_seq} mono />
                      )}
                    </div>
                  }
                />
                <ContextRow
                  title="Universal reverse primer"
                  ok={result.context.reverse_universal.matches}
                  note={result.context.reverse_universal.note}
                />
              </div>
            </section>
          )}

          {/* On-demand: BLAST + LNA */}
          <section className="space-y-3">
            <h2 className="text-sm font-semibold text-slate-600">Optional checks</h2>

            {blastMirnaId ? (
              <OffTargetPanel
                forwardPrimer={forward}
                reversePrimer={reverse}
                mirnaId={blastMirnaId}
              />
            ) : (
              <div className="rounded-lg border border-slate-200 overflow-hidden">
                <div className="px-3 py-2 bg-slate-50 border-b border-slate-200">
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Off-target Check (BLAST)</p>
                </div>
                <p className="px-3 py-3 text-xs text-slate-500 leading-relaxed">
                  Add the miRBase ID with its arm (e.g. <span className="font-mono text-slate-700">hsa-miR-21-5p</span>) above to run BLAST — the ID lets it exclude the primer's own on-target miRNA.
                </p>
              </div>
            )}

            {/* LNA Tm — gated: hidden while the backend LNA NN tables are unverified. */}
            {lnaEnabled && (
              <div className="rounded-lg border border-slate-200 overflow-hidden">
                <div className="px-3 py-2 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">LNA Tm (forward primer)</p>
                  <button
                    onClick={() => setShowLna((v) => !v)}
                    className="text-xs font-semibold px-3 py-1 rounded-lg border bg-amber-50 border-amber-300 text-amber-800 hover:bg-amber-100 transition-colors"
                  >
                    {showLna ? 'Hide' : 'Suggest LNA (Tm)'}
                  </button>
                </div>
                {showLna && (
                  <div className="p-3">
                    <LnaPanel
                      sequence={forward}
                      role="forward"
                      params={params}
                      mode="tm"
                      targetTm={params.annealingTemp || 60}
                      onClose={() => setShowLna(false)}
                    />
                  </div>
                )}
              </div>
            )}
          </section>

          {/* Method notes */}
          <section className="text-xs text-slate-400 border-t border-slate-100 pt-3 space-y-1">
            {result.meta?.method_notes?.map((n, i) => <p key={i}>{n}</p>)}
          </section>
        </div>
      )}
    </div>
  );
}

// ── Presentational helpers ────────────────────────────────────────

// Mature miRNA with the seed region (nt 2–8) highlighted.
function SeqWithSeed({ seq }) {
  if (!seq) return null;
  return (
    <span className="font-mono font-bold tracking-wide break-all text-sm">
      <span className="text-teal-800">{seq.slice(0, 1)}</span>
      <span className="bg-teal-100 text-teal-700 rounded px-0.5">{seq.slice(1, 8)}</span>
      <span className="text-teal-800">{seq.slice(8)}</span>
    </span>
  );
}

function PrimerInput({ label, accent, value, onChange, placeholder, hint }) {
  return (
    <div className={`rounded-lg border border-slate-200 border-l-4 ${accent} px-4 py-3 space-y-1.5 bg-slate-50/40`}>
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-sm font-semibold text-slate-700">{label}</span>
        {value && <span className="text-xs text-slate-400 tabular-nums">{value.replace(/\s/g, '').length} nt</span>}
      </div>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value.toUpperCase().replace(/\s/g, ''))}
        placeholder={placeholder}
        className="w-full font-mono text-sm px-3 py-2 rounded-lg border border-slate-200 focus:border-teal-400 focus:ring-1 focus:ring-teal-300 outline-none tracking-wide bg-white"
      />
      <p className="text-xs text-slate-400 leading-relaxed">{hint}</p>
    </div>
  );
}

const HAIRPIN_STYLE = {
  safe:       'text-teal-700',
  acceptable: 'text-teal-700',
  warning:    'text-amber-800',
  critical:   'text-red-700',
};

function PrimerCard({ title, data }) {
  if (!data) return null;
  const hp = data.hairpin ?? {};
  const sd = data.self_dimer ?? {};
  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm p-4 space-y-3">
      <div className="flex items-baseline justify-between gap-3 flex-wrap">
        <span className="text-sm font-semibold text-slate-700">{title}</span>
        <span className="font-mono text-xs text-slate-500 break-all">{data.sequence}</span>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-4 gap-y-2">
        <Metric label="Length"        value={`${data.length} nt`} />
        <Metric label="GC"            value={`${data.gc_percent}%`} />
        <Metric label="GC skew"       value={data.gc_skew} />
        <Metric label="Tm (NN)"       value={`${data.tm_nn} °C`} />
        <Metric label="3′-end stab."  value={`${data.end_stability_3prime} kcal/mol`} />
        <Metric label="Hairpin ΔG"    value={`${hp.dg} kcal/mol`} valueClass={HAIRPIN_STYLE[hp.severity] || 'text-slate-700'} />
        <Metric label="Self-dimer ΔG" value={`${sd.dg_overall} / ${sd.dg_3prime}`} valueClass={sd.critical_3prime ? 'text-red-700' : (!sd.pass_3prime ? 'text-amber-800' : 'text-slate-700')} />
        <Metric label="GC clamp"      value={data.gc_clamp?.pass ? 'OK' : 'weak'} valueClass={data.gc_clamp?.pass ? 'text-teal-700' : 'text-amber-800'} />
      </div>
      {(data.homopolymer_run || !data.gc_clamp?.pass || hp.severity === 'warning' || hp.severity === 'critical' || sd.critical_3prime) && (
        <ul className="text-xs space-y-0.5 pt-1 border-t border-slate-100">
          {data.homopolymer_run && <li className="text-amber-800">Homopolymer run &gt; 5 nt — may cause slippage.</li>}
          {!data.gc_clamp?.pass && <li className="text-amber-800">{data.gc_clamp?.reason}</li>}
          {(hp.severity === 'warning' || hp.severity === 'critical') && <li className={HAIRPIN_STYLE[hp.severity]}>{hp.note}</li>}
          {sd.critical_3prime && <li className="text-red-700">{sd.note}</li>}
        </ul>
      )}
      {data.tm_note && <p className="text-xs text-slate-400 leading-relaxed">{data.tm_note}</p>}
    </div>
  );
}

function Metric({ label, value, valueClass = 'text-slate-700' }) {
  return (
    <div className="space-y-0.5">
      <p className="text-xs text-slate-400">{label}</p>
      <p className={`text-sm font-semibold tabular-nums ${valueClass}`}>{value}</p>
    </div>
  );
}

function ContextRow({ title, ok, note, extra }) {
  return (
    <div className={`rounded-xl border px-4 py-3 ${ok ? 'border-teal-200 bg-teal-50/50' : 'border-amber-200 bg-amber-50/60'}`}>
      <div className="flex items-baseline gap-2">
        <span className={`text-xs font-bold ${ok ? 'text-teal-700' : 'text-amber-800'}`}>{ok ? '✓' : '⚠'}</span>
        <span className="text-sm font-semibold text-slate-700">{title}</span>
      </div>
      <p className="text-xs text-slate-600 leading-relaxed mt-1">{note}</p>
      {extra}
    </div>
  );
}

function Kv({ k, v, mono }) {
  return (
    <span className="inline-flex items-center gap-1 text-xs bg-white border border-slate-200 rounded px-2 py-0.5">
      <span className="text-slate-400">{k}</span>
      <span className={`text-slate-700 font-semibold ${mono ? 'font-mono' : ''}`}>{v}</span>
    </span>
  );
}

function dimerStatus(d) {
  if (d.critical_3prime) return { label: 'Critical', cls: 'text-red-700 bg-red-50 border-red-200' };
  if (!d.pass_overall || !d.pass_3prime) return { label: 'Watch', cls: 'text-amber-800 bg-amber-50 border-amber-200' };
  return { label: 'OK', cls: 'text-teal-700 bg-teal-50 border-teal-200' };
}

function fmt(x) {
  return typeof x === 'number' ? x.toFixed(2) : x;
}
