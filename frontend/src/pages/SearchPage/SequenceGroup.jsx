import { useEffect, useRef, useState } from 'react';
import Tooltip from '../../components/ui/Tooltip.jsx';
import CollapsibleSection from '../../components/ui/CollapsibleSection.jsx';
import { useMiRBase } from '../../hooks/useMiRBase.js';
import { SPECIES_OPTIONS } from '../../constants/defaults.js';

function detectInputType(query) {
  const q = query.trim();
  if (/^MIMAT\d+$/i.test(q)) return 'accession';
  if (/^[AUGCUT]+$/i.test(q) && q.length >= 10) return 'sequence';
  return 'name';
}

// Render sequence with nt 2–8 (0-indexed 1–7) highlighted as the seed region
function SeqWithSeed({ seq }) {
  if (!seq) return null;
  const pre  = seq.slice(0, 1);   // nt 1
  const seed = seq.slice(1, 8);   // nt 2–8  (seed region)
  const post = seq.slice(8);
  return (
    <span className="font-mono font-bold tracking-wide break-all">
      <span className="text-teal-800">{pre}</span>
      <span className="bg-teal-100 text-teal-700 rounded px-0.5">{seed}</span>
      <span className="text-teal-800">{post}</span>
    </span>
  );
}

export default function SequenceGroup({ data, errors, onChange, onError, seqAnalysis, openRequested }) {
  const { status, result, errorMessage, fetchMiRNA, reset } = useMiRBase();
  const prevQuery = useRef('');
  const [isSeqLookup, setIsSeqLookup] = useState(false);

  const onChangeRef = useRef(onChange);
  useEffect(() => { onChangeRef.current = onChange; });
  const onErrorRef = useRef(onError);
  useEffect(() => { onErrorRef.current = onError; });

  useEffect(() => {
    if (status === 'found' && result?.sequence) {
      onChangeRef.current('matureSequence', result.sequence);
      onChangeRef.current('mirnaName',      result.id        ?? '');
      onChangeRef.current('mirbaseId',      result.accession ?? '');
      onChangeRef.current('accession',      result.accession ?? '');
      onChangeRef.current('family',         result.family    ?? '');
      onErrorRef.current('matureSequence', '');
      const matched = SPECIES_OPTIONS.find(
        (s) => s.scientific === result.species || s.label.toLowerCase() === result.species?.toLowerCase()
      );
      if (matched) onChangeRef.current('species', matched.value);
    } else if (status === 'error' || status === 'not_found') {
      prevQuery.current = '';
    }
  }, [status, result]);

  function validateSequence(seq) {
    const clean = seq.trim().toUpperCase();
    if (/T/i.test(clean)) {
      onError('matureSequence', "Character 'T' detected. This must be an RNA sequence — use 'U' instead of 'T'.");
      return false;
    }
    if (/[^AUGC]/i.test(clean)) {
      onError('matureSequence', 'Only A, U, G, C are accepted.');
      return false;
    }
    if (clean.length < 15) {
      onError('matureSequence', 'Sequence too short. Mature miRNAs are typically 17–24 nt.');
      return false;
    }
    if (clean.length > 30) {
      onError('matureSequence', 'Sequence may be too long for a mature miRNA (typically 17–24 nt).');
      return false;
    }
    onError('matureSequence', '');
    onChange('matureSequence', clean);
    onChange('mirnaName', '');
    onChange('mirbaseId', '');
    onChange('accession', '');
    onChange('family', '');
    return true;
  }

  function handleSearch() {
    const query = data.searchQuery.trim();
    if (!query || query === prevQuery.current) return;
    prevQuery.current = query;

    const type = detectInputType(query);
    if (type === 'sequence') {
      reset();
      setIsSeqLookup(true);
      const valid = validateSequence(query);
      if (valid) fetchMiRNA(query); // reverse-lookup name/ID silently
    } else {
      setIsSeqLookup(false);
      onChange('matureSequence', '');
      onChange('mirnaName', '');
      onChange('mirbaseId', '');
      onError('matureSequence', '');
      fetchMiRNA(query);
    }
  }

  function handleQueryChange(e) {
    const val = e.target.value;
    onChange('searchQuery', val);
    prevQuery.current = '';
    if (!val.trim()) {
      onChange('matureSequence', '');
      onChange('mirnaName', '');
      onChange('mirbaseId', '');
      onChange('accession', '');
      onChange('family', '');
      onError('matureSequence', '');
      setIsSeqLookup(false);
      reset();
    }
  }

  const hasResult = seqAnalysis !== null && !errors.matureSequence;

  // Derive display name/ID directly from the hook result — never from stale formData
  const displayName = (status === 'found' && result) ? (result.id ?? '')        : '';
  const displayId   = (status === 'found' && result) ? (result.accession ?? '') : '';

  return (
    <CollapsibleSection
      title="Sequence Information"
      tooltip="Search by miRNA name, miRBase accession (MIMAT…), or paste the RNA sequence — the tool auto-detects the input type."
      defaultOpen
      hasError={!!errors.matureSequence}
      openRequested={openRequested}
    >
      {/* ── Unified search ─────────────────────────────────── */}
      <div className="space-y-2">
        <div>
          <label className="text-sm font-medium text-gray-700">Search miRNA</label>
          <p className="text-xs text-gray-400 mt-0.5">
            Enter a miRNA name, miRBase ID, or paste the mature sequence (A/U/G/C)
          </p>
        </div>

        <div className="flex gap-2">
          <input
            type="text"
            value={data.searchQuery}
            onChange={handleQueryChange}
            onKeyDown={(e) => (e.key === 'Enter' || e.key === 'Tab') && handleSearch()}
            placeholder="hsa-miR-21-5p · MIMAT0000076 · UAGCUUAUCAGACUGAUGUUGA"
            disabled={status === 'loading'}
            className="flex-1 text-sm border border-gray-200 rounded-lg px-3 py-2 text-gray-900 placeholder-gray-400 focus:outline-none focus:border-teal-300 focus:ring-1 focus:ring-teal-100 disabled:bg-gray-50 disabled:text-gray-400"
          />
          <button
            type="button"
            onClick={handleSearch}
            disabled={status === 'loading' || !data.searchQuery.trim()}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-teal-600 to-teal-800 text-white text-sm font-semibold
              shadow-sm hover:opacity-90 active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-150"
          >
            <svg viewBox="0 0 16 16" fill="none" className="w-4 h-4 shrink-0" aria-hidden="true">
              <circle cx="6.5" cy="6.5" r="4" stroke="currentColor" strokeWidth="1.7"/>
              <line x1="9.8" y1="9.8" x2="13.5" y2="13.5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round"/>
            </svg>
            Search
          </button>
        </div>

        {!isSeqLookup && (status === 'not_found' || status === 'error') && (
          <p className="text-xs text-red-600 bg-red-50 border border-red-400 rounded px-2 py-1">
            ✗ {errorMessage}
          </p>
        )}
        {errors.matureSequence && (
          <p className="text-xs text-red-600">{errors.matureSequence}</p>
        )}
      </div>

      {/* ── Result card ─────────────────────────────────────── */}
      {hasResult && (
        <div className="border border-teal-200 rounded-xl bg-teal-50/40 p-4 space-y-3">
          {/*
            3-column grid:  [label 5.5rem] [value flex-1] [badge auto]
            Each row aligns a result field with its corresponding stat badge.
          */}
          <div className="grid grid-cols-[5.5rem_1fr_auto] gap-x-3 gap-y-2.5 text-sm items-center">

            {/* Row 1 — miRNA Name + length */}
            <span className="text-gray-400 text-xs font-medium uppercase tracking-wide">Name</span>
            <span className="font-mono text-gray-900 font-semibold break-all">
              {displayName || <span className="text-gray-400 font-normal italic font-sans">—</span>}
            </span>
            <span className="text-xs bg-white border border-teal-200 text-teal-700 rounded-md px-2 py-0.5 font-semibold whitespace-nowrap">
              {seqAnalysis.length} nt
            </span>

            {/* Row 2 — miRBase ID + overall GC */}
            <span className="text-gray-400 text-xs font-medium uppercase tracking-wide">ID</span>
            <span className="font-mono text-gray-700 break-all">
              {displayId || <span className="text-gray-400 font-normal italic font-sans">—</span>}
            </span>
            <span className="text-xs bg-white border border-teal-200 text-teal-700 rounded-md px-2 py-0.5 whitespace-nowrap">
              GC {seqAnalysis.gcContent}%
            </span>

            {/* Row 3 — Sequence with seed highlighted + seed badge */}
            <span className="text-gray-400 text-xs font-medium uppercase tracking-wide leading-tight">
              Seq 5′→3′
            </span>
            <SeqWithSeed seq={data.matureSequence} />
            <span className="inline-flex items-center gap-1 text-xs bg-teal-50 border border-teal-300 text-teal-700 rounded-md px-2 py-0.5 whitespace-nowrap">
              <Tooltip text="Seed region: nt 2–8 from the 5′ end. Determines target mRNA recognition and discrimination between members of the same miRNA family." />
              Seed <span className="font-mono font-semibold">{seqAnalysis.seed7mer}</span>
              <span className="text-teal-500">· {seqAnalysis.gcSeed}%</span>
            </span>
          </div>

          {/* Warnings */}
          <div className="space-y-1.5 pt-1 border-t border-teal-100">
            {seqAnalysis.lengthCategory === 'short' && (
              <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 leading-relaxed">
                ⚠ <strong>Short sequence ({seqAnalysis.length} nt):</strong> Mature miRNAs are typically 18–25 nt. This may be a fragment or an incompletely processed miRNA — verify before designing primers.
              </p>
            )}
            {seqAnalysis.lengthCategory === 'long' && (
              <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 leading-relaxed">
                ⚠ <strong>Long sequence ({seqAnalysis.length} nt):</strong> This may be a pre-miRNA fragment or an extended isomiR. The algorithm can still proceed, but results should be carefully reviewed.
              </p>
            )}
            {seqAnalysis.gcContent < 30 && (
              <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 leading-relaxed">
                ⚠ <strong>Low GC ({seqAnalysis.gcContent}%):</strong> The sequence is AU-rich — both the RT primer overhang and the forward primer will have low Tm. Consider increasing the RT temperature and Mg²⁺ concentration to compensate.
              </p>
            )}
            {seqAnalysis.gcContent > 70 && (
              <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 leading-relaxed">
                ⚠ <strong>High GC ({seqAnalysis.gcContent}%):</strong> The sequence is GC-rich — risk of secondary structure within the primer. Ensure a thorough denaturation step before RT and check for self-complementarity.
              </p>
            )}
            {seqAnalysis.bindingRegionGC < 33 && (
              <p className="text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2 leading-relaxed">
                ✗ <strong>GC-poor binding region ({seqAnalysis.bindingRegionGC}%):</strong> The 3′-most 6 nt contain ≤ 2 G/C — the RT primer overhang will have very low Tm and may dissociate before cDNA synthesis. Consider increasing the RT reaction temperature or using a more thermostable reverse transcriptase.
              </p>
            )}
            {seqAnalysis.bindingRegionGC > 83 && (
              <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 leading-relaxed">
                ⚠ <strong>GC-rich binding region ({seqAnalysis.bindingRegionGC}%):</strong> The 3′-most 6 nt contain ≥ 5 G/C — the RT primer overhang may bind non-specifically to other GC-rich sites in the genome.
              </p>
            )}
            {seqAnalysis.bindingRegionHasRepeat && (
              <p className="text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2 leading-relaxed">
                ✗ <strong>Repeat in binding region ({seqAnalysis.bindingRegion}):</strong> The RT primer annealing site contains ≥ 3 identical consecutive nt — this directly affects cDNA fidelity and makes designing a specific overhang very difficult.
              </p>
            )}
            {!seqAnalysis.startsWithU && (
              <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 leading-relaxed">
                ⚠ <strong>Non-canonical 5′ end:</strong> The sequence does not start with U. Most mature miRNAs start with U for preferential loading into the Ago2 complex. Verify that this is a mature miRNA sequence.
              </p>
            )}
            {seqAnalysis.hasContinuousRepeat && (
              <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 leading-relaxed">
                ⚠ <strong>Homopolymer run detected:</strong> ≥ 4 identical consecutive nucleotides found. The algorithm will avoid using this region in primers if possible; if the run falls within the binding region it cannot be avoided.
              </p>
            )}
          </div>
        </div>
      )}
    </CollapsibleSection>
  );
}
