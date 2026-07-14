import { useEffect, useRef, useState } from 'react';
import { useHrmSession } from '../contexts/HrmSessionContext.jsx';

/**
 * ChatPanel — the grounded Q&A surface [SPEC_Phase1 §5, §6].
 *
 * A pure view. The conversation itself (messages, streaming, abort, citations) lives in
 * HrmSessionContext, because this component is mounted TWICE — full-size on /assistant and
 * `compact` in the sidebar — and both must show the same conversation. See that file for why
 * holding the transcript in component state was wrong.
 *
 * Two things this view must never hide:
 *   1. the guardrail warnings (§5.3) — an unverified number or a fabricated citation is shown
 *      ON the message, not swallowed;
 *   2. whether the HRM table was actually used, so "the model read my data" is a fact on screen
 *      rather than an assumption.
 */

const GENERIC_SUGGESTIONS = [
  'What causes a double melt peak in HRM?',
  'Why does a stem-loop RT primer improve miRNA specificity?',
  'How is Tm determined from a melt curve?',
];

export default function ChatPanel({ compact = false }) {
  const { hasHrm, messages, loading, followups, send, stop, resetChat } = useHrmSession();

  const [input, setInput] = useState('');

  const endRef        = useRef(null);
  const scrollerRef   = useRef(null);
  const stickToBottom = useRef(true);

  // A streaming answer would otherwise yank the view down while the user is scrolled up reading
  // an earlier message. Only auto-scroll when they are already at the bottom.
  useEffect(() => {
    if (stickToBottom.current) endRef.current?.scrollIntoView({ behavior: 'smooth' });
  });

  function onScroll() {
    const el = scrollerRef.current;
    if (!el) return;
    stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 60;
  }

  function submit(q) {
    stickToBottom.current = true;
    setInput('');
    send(q);
  }

  // With HRM loaded the backend supplies chips built from the user's own wells; without it, all
  // we can honestly offer is general protocol questions.
  const chips = messages.length === 0
    ? (hasHrm ? [] : GENERIC_SUGGESTIONS)
    : followups;

  return (
    <section
      className={
        compact
          ? 'flex flex-col h-full min-h-0'
          : 'flex flex-col h-full min-h-0 border border-gray-200 rounded-xl bg-white'
      }
    >
      {!compact && (
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-gray-100 shrink-0">
          <h2 className="text-sm font-semibold text-gray-700">Assistant</h2>
          <div className="flex items-center gap-2">
            {messages.length > 0 && !loading && (
              <button
                type="button"
                onClick={resetChat}
                className="text-[10px] text-gray-400 hover:text-gray-600 underline"
              >
                New chat
              </button>
            )}
            <HrmBadge hasHrm={hasHrm} />
          </div>
        </div>
      )}

      {/* Messages */}
      <div
        ref={scrollerRef}
        onScroll={onScroll}
        className={`flex-1 overflow-y-auto space-y-3 min-h-0 ${compact ? 'px-3 py-3' : 'px-4 py-3'}`}
      >
        {messages.length === 0 && (
          <div className="text-center py-6 space-y-3">
            {compact && <HrmBadge hasHrm={hasHrm} />}
            <p className="text-[11px] text-gray-400 max-w-sm mx-auto leading-relaxed">
              {hasHrm
                ? 'Answers are grounded in your ingested papers and the numeric table computed from your melt-curve file — never invented. Click a well in the table to ask about it.'
                : 'No melt-curve file loaded. Answers will come from your ingested papers only. Upload a file on the Assistant page to ask about your own results.'}
            </p>
          </div>
        )}

        {messages.map((m, i) => (
          <Message key={i} m={m} showSources={compact} />
        ))}

        <div ref={endRef} />
      </div>

      {/* Follow-up chips — real questions about the user's own wells */}
      {chips.length > 0 && !loading && (
        <div className={`flex flex-wrap gap-1.5 shrink-0 ${compact ? 'px-3 pb-2' : 'px-4 pb-2'}`}>
          {chips.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => submit(s)}
              className="text-[11px] text-left text-gray-500 border border-gray-200 rounded-full px-2.5 py-1
                         hover:border-teal-300 hover:text-teal-700 hover:bg-teal-50 transition-colors"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Composer */}
      <div className={`border-t border-gray-100 shrink-0 ${compact ? 'px-3 py-2.5' : 'px-4 py-3'}`}>
        <form onSubmit={(e) => { e.preventDefault(); submit(input); }} className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading}
            placeholder={hasHrm ? 'Ask about your HRM results…' : 'Ask about the protocol…'}
            className="flex-1 text-xs border border-gray-200 rounded-lg px-3 py-2
                       focus:outline-none focus:border-teal-400 focus:ring-1 focus:ring-teal-200
                       disabled:bg-gray-50 disabled:text-gray-400"
          />
          {loading ? (
            <button
              type="button"
              onClick={stop}
              title="Stop generating"
              className="px-3 py-2 rounded-lg bg-gray-100 text-gray-600 text-xs font-semibold
                         hover:bg-red-50 hover:text-red-600 transition-colors whitespace-nowrap"
            >
              ■ Stop
            </button>
          ) : (
            <button
              type="submit"
              disabled={!input.trim()}
              className="px-3 py-2 rounded-lg bg-teal-600 text-white text-xs font-semibold
                         hover:bg-teal-800 disabled:bg-gray-200 disabled:text-gray-400
                         disabled:cursor-not-allowed transition-colors"
            >
              Send
            </button>
          )}
        </form>
      </div>
    </section>
  );
}

function HrmBadge({ hasHrm }) {
  return (
    <span
      className={`inline-block text-[10px] font-semibold px-2 py-0.5 rounded-full border ${
        hasHrm
          ? 'text-teal-700 bg-teal-50 border-teal-200'
          : 'text-gray-400 bg-gray-50 border-gray-200'
      }`}
      title={hasHrm
        ? 'Answers can quote numbers from the uploaded HRM table.'
        : 'No HRM file uploaded — answers will come from papers only.'}
    >
      {hasHrm ? 'HRM data loaded' : 'No HRM data'}
    </span>
  );
}

function Message({ m, showSources }) {
  if (m.role === 'user') {
    return (
      <div className="flex justify-end">
        <p className="max-w-[85%] text-xs bg-teal-600 text-white rounded-xl rounded-br-sm px-3 py-2 leading-relaxed">
          {m.text}
        </p>
      </div>
    );
  }

  if (m.error) {
    return (
      <div className="border border-red-200 bg-red-50 rounded-xl px-3 py-2">
        <p className="text-xs font-semibold text-red-600">{m.text}</p>
        {m.message && <p className="text-[11px] text-red-500 mt-0.5 leading-snug">{m.message}</p>}
      </div>
    );
  }

  // Before the first token. On CPU the model spends a minute or two just READING the prompt
  // before it writes anything, so this state is long and needs to say something true. `meta`
  // lands almost immediately, so we can report that retrieval succeeded and how many papers it
  // found — evidence the request is alive, rather than a spinner that could equally mean the
  // backend has hung.
  if (m.streaming && !m.text) {
    const retrieved = m.sources?.length;
    return (
      <div className="space-y-1">
        <div className="flex items-center gap-2 text-[11px] text-gray-500">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-teal-500 animate-pulse" />
          {retrieved === undefined
            ? 'Searching the knowledge base…'
            : retrieved > 0
              ? `Found ${retrieved} source${retrieved > 1 ? 's' : ''}. Reading them…`
              : 'No matching papers. Reading the HRM table…'}
        </div>
        <p className="text-[10px] text-gray-300 leading-snug pl-3.5">
          A 7B model on CPU spends a minute or two reading the context before it starts writing.
          Press Stop to cancel.
        </p>
      </div>
    );
  }

  return (
    <div className="max-w-[92%] space-y-1.5">
      <div className="bg-gray-50 border border-gray-100 rounded-xl rounded-bl-sm px-3 py-2">
        <p className="text-xs text-gray-700 leading-relaxed whitespace-pre-wrap">
          {m.text}
          {m.streaming && (
            <span className="inline-block w-1.5 h-3 ml-0.5 -mb-0.5 bg-teal-500 animate-pulse" />
          )}
        </p>
        {m.stopped && (
          <p className="text-[10px] text-gray-400 mt-1 italic">Stopped — answer is incomplete.</p>
        )}
      </div>

      {/* Guardrail output [SPEC_Phase1 §5.3] — surfaced, never suppressed. */}
      {m.warnings?.length > 0 && (
        <div className="border border-amber-200 bg-amber-50 rounded-lg px-2.5 py-1.5 space-y-1">
          {m.warnings.map((w, i) => (
            <p key={i} className="text-[10px] text-amber-700 leading-snug">⚠ {w}</p>
          ))}
        </div>
      )}

      {/* In the sidebar there is no separate sources panel, so [n] must resolve here — otherwise
          the citations in the text point at nothing the user can open. */}
      {showSources && m.sources?.length > 0 && !m.streaming && (
        <ol className="space-y-1">
          {m.sources.map((s) => (
            <li key={s.n} className="text-[10px] leading-snug">
              <span className="font-bold text-teal-700">[{s.n}]</span>{' '}
              <a href={s.url} target="_blank" rel="noopener noreferrer"
                 className="text-gray-500 hover:text-teal-700 hover:underline">
                {s.title}
              </a>
              <span className="text-gray-300"> · {s.year}</span>
            </li>
          ))}
        </ol>
      )}

      {!m.streaming && (
        <div className="flex flex-wrap items-center gap-1.5">
          {m.usedHrm && (
            <span className="text-[10px] text-teal-700 bg-teal-50 border border-teal-200 rounded-full px-1.5 py-0.5">
              grounded in HRM table
            </span>
          )}
          {!showSources && m.sources?.length > 0 && (
            <span className="text-[10px] text-gray-500 bg-gray-50 border border-gray-200 rounded-full px-1.5 py-0.5">
              {m.sources.length} source{m.sources.length > 1 ? 's' : ''} → see panel
            </span>
          )}
          {m.blocked === 'phase2_scope' && (
            <span className="text-[10px] text-slate-600 bg-slate-100 border border-slate-200 rounded-full px-1.5 py-0.5">
              out of Phase 1 scope
            </span>
          )}
        </div>
      )}
    </div>
  );
}
