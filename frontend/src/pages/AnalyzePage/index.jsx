import { useState, useEffect } from 'react';
import axios from 'axios';
import { thermoForRequest } from '../../utils/designRequest.js';
import { fmtDg, fmtTm, fmtPct, withUnit, STATUS_CLASSES } from '../../utils/format.js';
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
  { key: 'saltConcentration',      label: 'Na⁺/K⁺ total', unit: 'mM', step: 1 },
  { key: 'kPlusConc',              label: 'Extra K⁺',   unit: 'mM', step: 1 },
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

  useEffect(() => { document.title = 'HG Lab | Primer analyzer'; }, []);
  // Remounts the search box so "Load example" fills it (it reads its initial query once).
  const [searchKey, setSearchKey] = useState(0);

  function loadExample() {
    setMirnaId(EXAMPLE.mirnaId);
    setMature(EXAMPLE.mature);
    setRt(EXAMPLE.rt);
    setForward(EXAMPLE.forward);
    setReverse(EXAMPLE.reverse);
    setSearchKey((k) => k + 1);
    setStatus('idle');
    setResult(null);
    setErrorMsg('');
  }

  function clearAll() {
    setMirnaId(''); setMature(''); setRt(''); setForward('');
    setReverse(UNIVERSAL_REVERSE);
    setSearchKey((k) => k + 1);
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
        // Default pH is not sent (no Tris term), as on /design: designRequest.thermoForRequest.
        params: thermoForRequest(params),
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
        <h1 className="text-xl font-bold text-slate-800">Primer analyzer</h1>
        <p className="text-sm text-slate-600 leading-relaxed">
          Paste an existing stem-loop RT-qPCR primer set and its mature miRNA to see the
          thermodynamic parameters, the cross-dimer risk and how each primer matches the miRNA.
          No design is run; your sequences are analyzed unchanged.
        </p>
      </div>

      {/* ── Input card ── */}
      <div className="rounded-2xl border border-slate-200 bg-white shadow-sm p-6 space-y-5">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-600">Input</h2>
          <div className="flex items-center gap-3 text-xs">
            <button type="button" onClick={loadExample} className="text-teal-700 hover:underline font-medium">Load example</button>
            <button type="button" onClick={clearAll} className="text-slate-600 hover:text-slate-800">Clear</button>
          </div>
        </div>

        {/* miRNA — unified search (name / miRBase ID / sequence) with autocomplete */}
        <div className="space-y-2">
          <div>
            <span className="text-xs font-medium text-slate-700">Mature miRNA</span>
            <span className="text-xs text-slate-600 ml-1">Type a name or accession for suggestions, or paste the RNA sequence (A/U/G/C).</span>
          </div>
          <MiRNASearchInput
            key={searchKey}
            initialQuery={mirnaId || mature}
            onResolve={(r) => { setMature((r.sequence || '').toUpperCase()); setMirnaId(r.id || ''); }}
            onRawSequence={(seq) => { setMature(seq); setMirnaId(''); }}
            onClear={() => { setMature(''); setMirnaId(''); }}
          />

          {mature && (
            <div className="border border-teal-200 rounded-xl bg-teal-50/40 px-4 py-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-sm">
              <span className="text-xs text-slate-600">miRNA</span>
              <span className="font-semibold text-slate-800 whitespace-nowrap">{mirnaId || '—'}</span>
              <SeqWithSeed seq={mature} />
              <span className="text-xs bg-white border border-teal-200 text-teal-700 rounded px-2 py-0.5 tabular-nums">{withUnit(mature.length, 'nt')}</span>
            </div>
          )}
        </div>

        {/* 3 primers */}
        <div className="space-y-4">
          <PrimerInput
            label="Stem-loop RT primer" accent="border-l-teal-400"
            value={rt} onChange={setRt}
            placeholder="GTCGTATCCAGTGCAGGGTCCGAGGTA…TCAACA"
            hint="Hairpin body + 3′ overhang complementary to the miRNA 3′ end; its length is read from the primer (standard 6 nt, 5-7 supported)"
          />
          <PrimerInput
            label="Forward qPCR primer" accent="border-l-teal-400"
            value={forward} onChange={setForward}
            placeholder="GCGGCGTAGCTTATCAGACTGA"
            hint="Synthetic 5′ tail + miRNA-specific 5′ region"
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
            type="button"
            aria-expanded={showParams}
            className="text-xs font-medium text-slate-700 hover:text-slate-900 flex items-start gap-1 text-left"
          >
            <span aria-hidden className={`transition-transform ${showParams ? 'rotate-90' : ''}`}>▸</span>
            <span>
              Reaction conditions
              {!showParams && (
                <span className="font-normal text-slate-600">
                  {' '}(defaults: Na⁺/K⁺ total {withUnit(DEFAULTS.thermodynamic.saltConcentration, 'mM')},{' '}
                  Mg²⁺ {withUnit(DEFAULTS.thermodynamic.magnesiumConcentration, 'mM')},{' '}
                  dNTP {withUnit(DEFAULTS.thermodynamic.dntpTotal, 'mM')},{' '}
                  primer {withUnit(DEFAULTS.thermodynamic.primerConcentration, 'nM')},{' '}
                  Ta {withUnit(DEFAULTS.qpcr.annealingTemp, '°C')})
                </span>
              )}
            </span>
          </button>
          {showParams && (
            <div className="mt-3 grid grid-cols-2 md:grid-cols-5 gap-3">
              {ION_FIELDS.map(({ key, label, unit, step }) => (
                <label key={key} className="block space-y-1">
                  <span className="block h-4 text-xs text-slate-700 whitespace-nowrap">{label}{unit ? `, ${unit}` : ''}</span>
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
            type="button"
            className="py-3 px-6 rounded-xl text-sm font-semibold transition-all bg-teal-600 text-white shadow-md hover:bg-teal-700 active:scale-[0.99] disabled:bg-slate-200 disabled:text-slate-700 disabled:shadow-none disabled:cursor-not-allowed"
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
        <div className="space-y-6" data-testid="analyze-results">

          {/* Per-primer metrics */}
          <section className="space-y-3">
            <h2 className="text-sm font-semibold text-slate-600">Per-primer parameters</h2>
            <div className="grid grid-cols-1 gap-3">
              <PrimerCard title="Stem-loop RT primer"      data={result.primers.rt} rt />
              <PrimerCard title="Forward qPCR primer"       data={result.primers.forward} />
              <PrimerCard title="Universal reverse primer"  data={result.primers.reverse} />
            </div>
          </section>

          {/* Cross-dimer matrix */}
          <section className="space-y-3">
            <h2 className="text-sm font-semibold text-slate-600">Cross-dimer matrix</h2>
            <div className="rounded-xl border border-slate-200 overflow-hidden bg-white">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 border-b border-slate-200 text-xs text-slate-700">
                  <tr>
                    <th className="text-left px-4 py-2 font-semibold">Pair</th>
                    <th className="text-right px-4 py-2 font-semibold">ΔG overall (kcal/mol)</th>
                    <th className="text-right px-4 py-2 font-semibold">ΔG 3′ end (kcal/mol)</th>
                    <th className="text-center px-4 py-2 font-semibold">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {result.cross_dimers.map((d) => {
                    const s = dimerStatus(d);
                    return (
                      <tr key={d.pair} title={d.note}>
                        <td className="px-4 py-2.5 font-medium text-slate-700">{d.pair}</td>
                        <td className="px-4 py-2.5 text-right tabular-nums text-slate-700">{fmtDg(d.dg_overall)}</td>
                        <td className="px-4 py-2.5 text-right tabular-nums text-slate-700">{fmtDg(d.dg_3prime)}</td>
                        <td className="px-4 py-2.5 text-center">
                          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full border ${s.cls}`}>{s.label}</span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <p className="text-xs text-slate-600">More negative ΔG means a more stable dimer. A stable 3′-end dimer is the concern: the polymerase can extend it into primer-dimer artifacts.</p>
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
                      {result.context.rt_overhang.hybrid_tm_c != null
                        && (result.context.rt_overhang.overhang_length ?? 0) >= SHORT_DUPLEX_NT && (
                        <Kv k="hybrid Tm" v={fmtTm(result.context.rt_overhang.hybrid_tm_c)} />
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
                      <Kv k="matched" v={withUnit(result.context.forward_anchor.matched_len, 'nt')} />
                      <Kv k="tail ≈" v={withUnit(result.context.forward_anchor.tail_len, 'nt')} />
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
                mirnaSequence={mature}
              />
            ) : (
              <div className="rounded-lg border border-slate-200 overflow-hidden">
                <div className="px-3 py-2 bg-slate-50 border-b border-slate-200">
                  <p className="text-xs font-semibold text-slate-500">Off-target check (BLAST)</p>
                </div>
                <p className="px-3 py-3 text-xs text-slate-600 leading-relaxed">
                  Add the miRBase name with its arm (for example <span className="whitespace-nowrap text-slate-800">hsa-miR-21-5p</span>) above to run BLAST: the name lets it exclude the primer's own target.
                </p>
              </div>
            )}

            {/* LNA Tm — gated: hidden while the backend LNA NN tables are unverified. */}
            {lnaEnabled && (
              <div className="rounded-lg border border-slate-200 overflow-hidden">
                <div className="px-3 py-2 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
                  <p className="text-xs font-semibold text-slate-500">LNA Tm (forward primer)</p>
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
          <section className="text-xs text-slate-600 border-t border-slate-100 pt-3 space-y-1">
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
    <span className="seq font-bold text-sm">
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
        {value && <span className="text-xs text-slate-500 tabular-nums">{value.replace(/\s/g, '').length} nt</span>}
      </div>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value.toUpperCase().replace(/\s/g, ''))}
        placeholder={placeholder}
        className="w-full font-mono text-sm px-3 py-2 rounded-lg border border-slate-200 focus:border-teal-400 focus:ring-1 focus:ring-teal-300 outline-none bg-white"
      />
      <p className="text-xs text-slate-500 leading-relaxed">{hint}</p>
    </div>
  );
}

const HAIRPIN_STYLE = {
  safe:       'text-green-700',
  acceptable: 'text-green-700',
  warning:    'text-amber-800',
  critical:   'text-red-700',
};

// Overhang shorter than this: no point hybrid Tm (backend SHORT_DUPLEX_NT_THRESHOLD, as on /results).
const SHORT_DUPLEX_NT = 8;

function PrimerCard({ title, data, rt = false }) {
  if (!data) return null;
  const hp = data.hairpin ?? {};
  const sd = data.self_dimer ?? {};
  // Two stem-loop RT primers always pair through their shared 44-nt body: expected, used
  // at low concentration and refolded before RT — information, not a defect.
  const sdInfo = rt && !sd.pass_overall;
  const sdClass = sdInfo ? 'text-slate-800'
    : sd.critical_3prime ? 'text-red-700' : (!sd.pass_3prime ? 'text-amber-800' : 'text-slate-800');
  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm p-4 space-y-3">
      <div className="flex items-baseline justify-between gap-3 flex-wrap">
        <span className="text-sm font-semibold text-slate-800">{title}</span>
        <span className="seq-block text-xs text-slate-700 max-w-full">5′-{data.sequence}-3′</span>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-4 gap-y-2">
        <Metric label="Length"        value={withUnit(data.length, 'nt')} />
        <Metric label="GC"            value={fmtPct(data.gc_percent)} />
        <Metric label="Tm (nearest-neighbour)" value={fmtTm(data.tm_nn)} />
        <Metric label="3′-end stability (−ΔG)" value={`${fmtDg(data.end_stability_3prime)} kcal/mol`} />
        <Metric label="Hairpin ΔG"    value={`${fmtDg(hp.dg)} kcal/mol`} valueClass={HAIRPIN_STYLE[hp.severity] || 'text-slate-800'} />
        <Metric label="Self-dimer ΔG, overall" value={`${fmtDg(sd.dg_overall)} kcal/mol`} valueClass={sdClass} />
        <Metric label="Self-dimer ΔG, 3′ end"  value={`${fmtDg(sd.dg_3prime)} kcal/mol`} valueClass={sdClass} />
        <Metric label="GC clamp"      value={data.gc_clamp?.pass ? 'Pass' : 'Warning'} valueClass={data.gc_clamp?.pass ? 'text-green-700' : 'text-amber-800'} />
      </div>
      {(data.homopolymer_run || !data.gc_clamp?.pass || hp.severity === 'warning' || hp.severity === 'critical' || sd.critical_3prime || sdInfo) && (
        <ul className="text-xs space-y-0.5 pt-1 border-t border-slate-100">
          {data.homopolymer_run && <li className="text-amber-800">Homopolymer run longer than 5 nt: may cause slippage.</li>}
          {!data.gc_clamp?.pass && <li className="text-amber-800">{data.gc_clamp?.reason}</li>}
          {(hp.severity === 'warning' || hp.severity === 'critical') && <li className={HAIRPIN_STYLE[hp.severity]}>{hp.note}</li>}
          {sdInfo
            ? <li className="text-slate-700"><span className="font-semibold">Information:</span> two stem-loop RT primers pair through their shared stem. This is expected for every stem-loop RT primer; at low concentration and refolded before RT it is not a design defect.</li>
            : sd.critical_3prime && <li className="text-red-700">{sd.note}</li>}
        </ul>
      )}
      {data.tm_note && <p className="text-xs text-slate-600 leading-relaxed">{data.tm_note}</p>}
    </div>
  );
}

function Metric({ label, value, valueClass = 'text-slate-700' }) {
  return (
    <div className="space-y-0.5">
      <p className="text-xs text-slate-600">{label}</p>
      <p className={`text-sm font-semibold tabular-nums ${valueClass}`}>{value}</p>
    </div>
  );
}

function ContextRow({ title, ok, note, extra }) {
  return (
    <div className={`rounded-xl border px-4 py-3 ${ok ? STATUS_CLASSES.Pass : STATUS_CLASSES.Warning}`}>
      <div className="flex items-baseline gap-2">
        <span className="text-xs font-bold">{ok ? 'Pass' : 'Warning'}</span>
        <span className="text-sm font-semibold text-slate-800">{title}</span>
      </div>
      <p className="text-xs text-slate-600 leading-relaxed mt-1">{note}</p>
      {extra}
    </div>
  );
}

function Kv({ k, v, mono }) {
  return (
    <span className="inline-flex items-center gap-1 text-xs bg-white border border-slate-200 rounded px-2 py-0.5">
      <span className="text-slate-600">{k}</span>
      <span className={`text-slate-800 font-semibold ${mono ? 'seq' : ''}`}>{v}</span>
    </span>
  );
}

function dimerStatus(d) {
  if (d.critical_3prime) return { label: 'Fail', cls: STATUS_CLASSES.Fail };
  if (!d.pass_overall || !d.pass_3prime) return { label: 'Warning', cls: STATUS_CLASSES.Warning };
  return { label: 'Pass', cls: STATUS_CLASSES.Pass };
}
