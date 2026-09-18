/**
 * MiRNASearchInput — unified miRNA search box with miRBase autocomplete.
 *
 * Self-contained: owns its query text, suggestion dropdown, and miRBase
 * lookup. Emits outward only through callbacks so it can be dropped into any
 * page (Designer uses its own SequenceGroup; this powers the Analyzer).
 *
 *   onResolve({ id, accession, sequence, family, species, length })
 *       — a name/accession was looked up (or a pasted sequence reverse-resolved)
 *   onRawSequence(cleanRNA)
 *       — the user pasted a valid RNA sequence directly (no DB hit yet)
 *   onClear()
 *       — the box was emptied
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import axios from 'axios';
import { useMiRBase } from '../hooks/useMiRBase.js';

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

function detectInputType(q) {
  const s = q.trim();
  if (/^MIMAT\d+$/i.test(s)) return 'accession';
  if (/^[AUGCT]+$/i.test(s)) return 'sequence';
  return 'name';
}

export default function MiRNASearchInput({ onResolve, onRawSequence, onClear, placeholder, initialQuery = '' }) {
  const { status, result, errorMessage, fetchMiRNA, reset } = useMiRBase();
  // `initialQuery` seeds the box once (used to restore a persisted draft on
  // remount); later edits are driven by the user, so it is not a controlled prop.
  const [query, setQuery] = useState(initialQuery);
  const [isSeqLookup, setIsSeqLookup] = useState(false);
  const [localError, setLocalError] = useState('');
  const prevQuery = useRef('');

  const [suggestions, setSuggestions]       = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [activeSuggIdx, setActiveSuggIdx]   = useState(-1);
  const [isFetchingSugg, setIsFetchingSugg] = useState(false);
  const [dropdownRect, setDropdownRect]     = useState(null);
  const suggestTimer = useRef(null);
  const wrapperRef = useRef(null);
  const inputRef   = useRef(null);

  const onResolveRef = useRef(onResolve);
  useEffect(() => { onResolveRef.current = onResolve; });

  useEffect(() => () => clearTimeout(suggestTimer.current), []);

  useEffect(() => {
    function handleClickOutside(e) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) setShowSuggestions(false);
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const updateDropdownRect = useCallback(() => {
    if (!inputRef.current) return;
    const r = inputRef.current.getBoundingClientRect();
    setDropdownRect({ top: r.bottom + 6, left: r.left, width: r.width });
  }, []);

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

  // Emit resolved miRNA to the parent when a lookup succeeds.
  useEffect(() => {
    if (status === 'found' && result?.sequence) {
      onResolveRef.current?.(result);
      setLocalError('');
    }
  }, [status, result]);

  const fetchSuggestions = useCallback(async (q) => {
    if (q.length < 2 || /^[AUGCT]+$/i.test(q) || /^MIMAT/i.test(q)) {
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
      setActiveSuggIdx(-1);
    } catch {
      setSuggestions([]);
      setShowSuggestions(false);
    } finally {
      setIsFetchingSugg(false);
    }
  }, [updateDropdownRect]);

  function validateSequence(seq) {
    const clean = seq.trim().toUpperCase();
    if (/T/i.test(clean)) { setLocalError("Character 'T' detected — this must be RNA. Use 'U' instead of 'T'."); return null; }
    if (/[^AUGC]/i.test(clean)) { setLocalError('Only A, U, G, C are accepted.'); return null; }
    if (clean.length < 15) { setLocalError('Sequence too short. Mature miRNAs are typically 17–24 nt.'); return null; }
    if (clean.length > 30) { setLocalError('Sequence too long for a mature miRNA (typically 17–24 nt).'); return null; }
    setLocalError('');
    return clean;
  }

  function handleSearch() {
    const q = query.trim();
    if (!q || q === prevQuery.current) return;
    prevQuery.current = q;
    const type = detectInputType(q);
    if (type === 'sequence') {
      reset();
      setIsSeqLookup(true);
      const clean = validateSequence(q);
      if (clean) {
        onRawSequence?.(clean);
        fetchMiRNA(clean); // reverse-lookup name/ID silently (nice-to-have)
      }
    } else {
      setIsSeqLookup(false);
      setLocalError('');
      fetchMiRNA(q);
    }
  }

  function selectSuggestion(item) {
    setQuery(item.name);
    prevQuery.current = '';
    setShowSuggestions(false);
    setSuggestions([]);
    setIsSeqLookup(false);
    setLocalError('');
    fetchMiRNA(item.name);
  }

  function handleQueryChange(e) {
    const val = e.target.value;
    setQuery(val);
    prevQuery.current = '';
    if (!val.trim()) {
      setSuggestions([]);
      setShowSuggestions(false);
      setIsFetchingSugg(false);
      setIsSeqLookup(false);
      setLocalError('');
      reset();
      onClear?.();
    } else {
      clearTimeout(suggestTimer.current);
      suggestTimer.current = setTimeout(() => fetchSuggestions(val), 200);
    }
  }

  function handleKeyDown(e) {
    if (!showSuggestions || suggestions.length === 0) {
      if (e.key === 'Enter') handleSearch();
      if (e.key === 'Tab') setShowSuggestions(false);
      return;
    }
    if (e.key === 'ArrowDown') { e.preventDefault(); setActiveSuggIdx((i) => Math.min(i + 1, suggestions.length - 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActiveSuggIdx((i) => Math.max(i - 1, -1)); }
    else if (e.key === 'Enter') {
      e.preventDefault();
      if (activeSuggIdx >= 0) selectSuggestion(suggestions[activeSuggIdx]);
      else { setShowSuggestions(false); handleSearch(); }
    } else if (e.key === 'Escape') { setShowSuggestions(false); setActiveSuggIdx(-1); }
    else if (e.key === 'Tab') { setShowSuggestions(false); handleSearch(); }
  }

  const showError = localError || (!isSeqLookup && (status === 'not_found' || status === 'error') ? errorMessage : '');

  return (
    <div className="space-y-2">
      <div className="flex gap-2" ref={wrapperRef}>
        <div className="relative flex-1">
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={handleQueryChange}
            onKeyDown={handleKeyDown}
            onFocus={() => {
              if (suggestions.length > 0 || isFetchingSugg) { updateDropdownRect(); setShowSuggestions(true); }
            }}
            placeholder={placeholder || 'hsa-miR-21-5p · MIMAT0000076 · UAGCUUAUCAGACUGAUGUUGA'}
            disabled={status === 'loading'}
            className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 text-slate-900 placeholder-slate-400 focus:outline-none focus:border-teal-400 focus:ring-1 focus:ring-teal-100 disabled:bg-slate-50 disabled:text-slate-400"
          />

          {showSuggestions && dropdownRect && createPortal(
            <div
              className="bg-white border border-slate-200 rounded-xl shadow-xl overflow-hidden"
              style={{ position: 'fixed', top: dropdownRect.top, left: dropdownRect.left, width: Math.max(dropdownRect.width, 420), zIndex: 9999 }}
            >
              <div className="flex items-center justify-between px-3 py-2 border-b border-slate-100 bg-slate-50">
                <span className="text-xs font-medium text-slate-500 uppercase tracking-wide">
                  {isFetchingSugg ? 'Searching…' : `${suggestions.length} suggestion${suggestions.length !== 1 ? 's' : ''}`}
                </span>
                <span className="text-[10px] text-slate-400">↑↓ navigate · Enter select · Esc close</span>
              </div>

              {isFetchingSugg && (
                <div className="px-3 py-2 space-y-2">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="flex items-center gap-3 animate-pulse">
                      <div className="w-4 h-4 rounded bg-slate-100 shrink-0" />
                      <div className="h-3.5 bg-slate-100 rounded w-40" />
                      <div className="h-3 bg-slate-100 rounded w-24 ml-auto" />
                    </div>
                  ))}
                </div>
              )}

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
                        className={`flex items-center gap-3 px-3 py-2.5 cursor-pointer transition-colors border-b border-slate-50 last:border-0 ${idx === activeSuggIdx ? 'bg-teal-50' : 'hover:bg-slate-50'}`}
                      >
                        <svg className={`w-3.5 h-3.5 shrink-0 ${idx === activeSuggIdx ? 'text-teal-500' : 'text-slate-300'}`} viewBox="0 0 16 16" fill="none">
                          <circle cx="6.5" cy="6.5" r="4" stroke="currentColor" strokeWidth="1.6" />
                          <line x1="9.8" y1="9.8" x2="13" y2="13" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
                        </svg>
                        <span className="font-mono text-sm text-slate-800 font-medium flex-1 min-w-0 truncate">
                          <Highlight text={item.name} query={query} />
                        </span>
                        {item.accession && <span className="text-[11px] font-mono text-slate-400 shrink-0">{item.accession}</span>}
                        <span className={`text-[11px] px-1.5 py-0.5 rounded font-medium shrink-0 ${isHuman ? 'bg-teal-50 text-teal-600 border border-teal-100' : 'bg-slate-100 text-slate-500'}`}>
                          {speciesShort}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              )}

              {!isFetchingSugg && suggestions.length === 0 && (
                <div className="px-4 py-5 text-center">
                  <p className="text-sm text-slate-500">No miRNA found matching <span className="font-mono font-medium">"{query}"</span></p>
                  <p className="text-xs text-slate-400 mt-1">Try a different name, or paste the sequence directly</p>
                </div>
              )}
            </div>,
            document.body
          )}
        </div>

        <button
          type="button"
          onClick={handleSearch}
          disabled={status === 'loading' || !query.trim()}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-teal-600 to-teal-800 text-white text-sm font-semibold shadow-sm hover:opacity-90 active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-150"
        >
          <svg viewBox="0 0 16 16" fill="none" className="w-4 h-4 shrink-0" aria-hidden="true">
            <circle cx="6.5" cy="6.5" r="4" stroke="currentColor" strokeWidth="1.7" />
            <line x1="9.8" y1="9.8" x2="13.5" y2="13.5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
          </svg>
          {status === 'loading' ? 'Searching…' : 'Search'}
        </button>
      </div>

      {showError && (
        <p className="text-xs text-red-700 bg-red-50 border border-red-200 rounded-lg px-2.5 py-1.5">{showError}</p>
      )}
    </div>
  );
}
