import { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import axios from 'axios';
import Tooltip from '../../components/ui/Tooltip.jsx';
import CollapsibleSection from '../../components/ui/CollapsibleSection.jsx';
import { useMiRBase } from '../../hooks/useMiRBase.js';
import { SPECIES_OPTIONS } from '../../constants/defaults.js';

/** Highlight the query substring inside `text` with a teal bold span. */
function Highlight({ text, query }) {
  if (!query) return <>{text}</>;
  const idx = text.toLowerCase().indexOf(query.toLowerCase());
  if (idx === -1) return <>{text}</>;
  return (
    <>
      {text.slice(0, idx)}
      <span className="text-teal-700 font-bold">{text.slice(idx, idx + query.length)}</span>
      {text.slice(idx + query.length)}
    </>
  );
}

function detectInputType(query) {
  const q = query.trim();
  if (/^MIMAT\d+$/i.test(q)) return 'accession';
  if (/^[AUGCUT]+$/i.test(q)) return 'sequence';
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

  // Autocomplete state
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [activeSuggIdx, setActiveSuggIdx] = useState(-1);
  const [isFetchingSugg, setIsFetchingSugg] = useState(false);
  const [dropdownRect, setDropdownRect] = useState(null);
  const suggestTimer = useRef(null);
  const wrapperRef = useRef(null);
  const inputRef = useRef(null);

  const onChangeRef = useRef(onChange);
  useEffect(() => { onChangeRef.current = onChange; });
  const onErrorRef = useRef(onError);
  useEffect(() => { onErrorRef.current = onError; });

  // Clear debounce timer on unmount to avoid state updates on a dead component
  useEffect(() => () => clearTimeout(suggestTimer.current), []);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(e) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setShowSuggestions(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Recalculate dropdown position anchored to input element
  const updateDropdownRect = useCallback(() => {
    if (!inputRef.current) return;
    const r = inputRef.current.getBoundingClientRect();
    setDropdownRect({ top: r.bottom + 6, left: r.left, width: r.width });
  }, []);

  // Keep portal position in sync while visible
  useEffect(() => {
    if (!showSuggestions) return;
    updateDropdownRect();
    window.addEventListener('scroll', updateDropdownRect, true);
    window.addEventListener('resize', updateDropdownRect);
    return () => {
      window.removeEventListener('scroll', updateDropdownRect, true);
      window.removeEventListener('resize', updateDropdownRect);
    };
  }, [showSuggestions, updateDropdownRect]);

  const fetchSuggestions = useCallback(async (q) => {
    if (q.length < 2 || /^[AUGCUT]+$/i.test(q) || /^MIMAT/i.test(q)) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }
    updateDropdownRect();
    setIsFetchingSugg(true);
    setShowSuggestions(true);
    try {
      const { data: items } = await axios.get('/api/mirbase/suggest', { params: { q } });
      setSuggestions(items);
      setShowSuggestions(true);
      setActiveSuggIdx(-1);
    } catch {
      setSuggestions([]);
      setShowSuggestions(false);
    } finally {
      setIsFetchingSugg(false);
    }
  }, [updateDropdownRect]);

  useEffect(() => {
    if (status === 'found' && result?.sequence) {
      onChangeRef.current('matureSequence', result.sequence);
      // When looked up by name/accession, replace the search field with the resolved sequence
      // so the input reflects the actual RNA used for design
      if (!isSeqLookup) {
        onChangeRef.current('searchQuery', result.sequence);
      }
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
  }, [status, result, isSeqLookup]);

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

  function selectSuggestion(item) {
    onChange('searchQuery', item.name);
    prevQuery.current = '';
    setShowSuggestions(false);
    setSuggestions([]);
    // Trigger search immediately
    fetchMiRNA(item.name);
    setIsSeqLookup(false);
    onChange('matureSequence', '');
    onChange('mirnaName', '');
    onChange('mirbaseId', '');
    onError('matureSequence', '');
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
      setSuggestions([]);
      setShowSuggestions(false);
      setIsFetchingSugg(false);
      reset();
    } else {
      clearTimeout(suggestTimer.current);
      suggestTimer.current = setTimeout(() => fetchSuggestions(val), 200);
    }
  }

  function handleKeyDown(e) {
    if (!showSuggestions || suggestions.length === 0) {
      if (e.key === 'Enter') handleSearch();
      if (e.key === 'Tab') setShowSuggestions(false); // close without triggering search while loading
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveSuggIdx(i => Math.min(i + 1, suggestions.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveSuggIdx(i => Math.max(i - 1, -1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (activeSuggIdx >= 0) selectSuggestion(suggestions[activeSuggIdx]);
      else { setShowSuggestions(false); handleSearch(); }
    } else if (e.key === 'Escape') {
      setShowSuggestions(false);
      setActiveSuggIdx(-1);
    } else if (e.key === 'Tab') {
      setShowSuggestions(false);
      handleSearch();
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

        <div className="flex gap-2" ref={wrapperRef}>
          <div className="relative flex-1">
            <input
              ref={inputRef}
              type="text"
              value={data.searchQuery}
              onChange={handleQueryChange}
              onKeyDown={handleKeyDown}
              onFocus={() => {
                if (suggestions.length > 0 || isFetchingSugg) {
                  updateDropdownRect();
                  setShowSuggestions(true);
                }
              }}
              placeholder="hsa-miR-21-5p · MIMAT0000076 · UAGCUUAUCAGACUGAUGUUGA"
              disabled={status === 'loading'}
              className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 text-gray-900 placeholder-gray-400 focus:outline-none focus:border-teal-300 focus:ring-1 focus:ring-teal-100 disabled:bg-gray-50 disabled:text-gray-400"
            />

            {/* ── Suggestions dropdown — rendered via portal to escape overflow:hidden parents ── */}
            {showSuggestions && dropdownRect && createPortal(
              <div
                className="bg-white border border-gray-200 rounded-xl shadow-xl overflow-hidden"
                style={{
                  position: 'fixed',
                  top: dropdownRect.top,
                  left: dropdownRect.left,
                  width: Math.max(dropdownRect.width, 420),
                  zIndex: 9999,
                }}
              >

                {/* Header */}
                <div className="flex items-center justify-between px-3 py-2 border-b border-gray-100 bg-gray-50">
                  <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                    {isFetchingSugg ? 'Searching…' : `${suggestions.length} suggestion${suggestions.length !== 1 ? 's' : ''}`}
                  </span>
                  <span className="text-[10px] text-gray-400">↑↓ navigate · Enter select · Esc close</span>
                </div>

                {/* Loading skeleton */}
                {isFetchingSugg && (
                  <div className="px-3 py-2 space-y-2">
                    {[1, 2, 3].map(i => (
                      <div key={i} className="flex items-center gap-3 animate-pulse">
                        <div className="w-4 h-4 rounded bg-gray-100 shrink-0" />
                        <div className="h-3.5 bg-gray-100 rounded w-40" />
                        <div className="h-3 bg-gray-100 rounded w-24 ml-auto" />
                      </div>
                    ))}
                  </div>
                )}

                {/* Results */}
                {!isFetchingSugg && suggestions.length > 0 && (
                  <ul>
                    {suggestions.map((item, idx) => {
                      const speciesShort = item.species === 'Homo sapiens' ? 'Human'
                        : item.species === 'Mus musculus' ? 'Mouse'
                        : item.species === 'Rattus norvegicus' ? 'Rat'
                        : item.species || '—';
                      const isHuman = item.species === 'Homo sapiens';
                      return (
                        <li
                          key={item.name}
                          onMouseDown={(e) => { e.preventDefault(); selectSuggestion(item); }}
                          onMouseEnter={() => setActiveSuggIdx(idx)}
                          className={`flex items-center gap-3 px-3 py-2.5 cursor-pointer transition-colors border-b border-gray-50 last:border-0 ${
                            idx === activeSuggIdx ? 'bg-teal-50' : 'hover:bg-gray-50'
                          }`}
                        >
                          {/* Icon */}
                          <svg className={`w-3.5 h-3.5 shrink-0 ${idx === activeSuggIdx ? 'text-teal-500' : 'text-gray-300'}`}
                               viewBox="0 0 16 16" fill="none">
                            <circle cx="6.5" cy="6.5" r="4" stroke="currentColor" strokeWidth="1.6"/>
                            <line x1="9.8" y1="9.8" x2="13" y2="13" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/>
                          </svg>

                          {/* Name with highlight */}
                          <span className="font-mono text-sm text-gray-800 font-medium flex-1 min-w-0 truncate">
                            <Highlight text={item.name} query={data.searchQuery} />
                          </span>

                          {/* Accession badge */}
                          {item.accession && (
                            <span className="text-[11px] font-mono text-gray-400 shrink-0">
                              {item.accession}
                            </span>
                          )}

                          {/* Species badge */}
                          <span className={`text-[11px] px-1.5 py-0.5 rounded font-medium shrink-0 ${
                            isHuman
                              ? 'bg-teal-50 text-teal-600 border border-teal-100'
                              : 'bg-gray-100 text-gray-500'
                          }`}>
                            {speciesShort}
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                )}

                {/* Empty state */}
                {!isFetchingSugg && suggestions.length === 0 && (
                  <div className="px-4 py-5 text-center">
                    <p className="text-sm text-gray-500">No miRNA found matching <span className="font-mono font-medium">"{data.searchQuery}"</span></p>
                    <p className="text-xs text-gray-400 mt-1">Try a different name, or paste the sequence directly</p>
                  </div>
                )}
              </div>,
              document.body
            )}
          </div>
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
