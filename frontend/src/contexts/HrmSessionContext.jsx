import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react';
import { askQuestionStream } from '../api/chatApi.js';

/**
 * HrmSessionContext — the assistant's whole session: the HRM analysis AND the conversation.
 *
 * Both live here, not inside ChatPanel, for two reasons:
 *
 *   1. THERE IS ONE ASSISTANT, SO THERE IS ONE CONVERSATION. ChatPanel is mounted twice — on
 *      /assistant and in the sidebar that follows the user across every page. With the
 *      transcript in component state those were two separate chats that happened to look alike:
 *      ask something in the sidebar and the page panel knew nothing about it.
 *
 *   2. NAVIGATION MUST NOT DESTROY THE CHAT. Component state dies with the component, so
 *      clicking "Designer" and coming back wiped the conversation — including a 3-minute answer
 *      the user was still reading.
 *
 * Owning send() here also deletes a hack. When both panels watched a shared "pending question",
 * both fired it: two LLM calls per click, which on CPU doubled the wait. That needed a claim
 * token to arbitrate. With one send() in one place, there is nothing to arbitrate.
 *
 * Session-scoped on purpose: the backend keeps the HRM numbers in memory for one sitting
 * (SPEC_Phase1 §0 — the data never leaves the machine), so persisting across a reload would only
 * produce a session_id the backend has already forgotten.
 */
const HrmSessionContext = createContext(null);

export function HrmSessionProvider({ children }) {
  const [hrm, setHrmState] = useState(null);

  const [messages, setMessages]   = useState([]);
  const [loading, setLoading]     = useState(false);
  const [followups, setFollowups] = useState([]);
  const [sources, setSources]     = useState([]);

  // Accumulated [{n, pmid}]. Held in a ref so send() does not need it as a dependency: it is
  // read at call time, never rendered.
  const citationsRef = useRef([]);
  const abortRef     = useRef(null);

  const send = useCallback(async (question) => {
    const q = (question ?? '').trim();
    if (!q || loading) return;

    // The transcript sent to the backend must not include the turn being asked right now.
    const history = messages
      .filter((m) => !m.error && m.text)
      .map((m) => ({ role: m.role, content: m.text }));

    setFollowups([]);
    setMessages((m) => [
      ...m,
      { role: 'user', text: q },
      { role: 'assistant', text: '', streaming: true, sources: [], warnings: [] },
    ]);
    setLoading(true);

    const controller = new AbortController();
    abortRef.current = controller;

    // Patch the LAST message in place on every token. Rebuilding the whole array per token
    // would re-render the entire transcript hundreds of times per answer.
    const patchLast = (patch) =>
      setMessages((prev) => {
        if (prev.length === 0) return prev;
        const next = [...prev];
        const i = next.length - 1;
        next[i] = typeof patch === 'function' ? patch(next[i]) : { ...next[i], ...patch };
        return next;
      });

    try {
      await askQuestionStream(
        { question: q, sessionId: hrm?.session_id, history,
          citations: citationsRef.current, signal: controller.signal },
        {
          onMeta: ({ sources: srcs, citations, usedHrm }) => {
            citationsRef.current = citations;
            patchLast({ sources: srcs, usedHrm });
            setSources(srcs);
          },
          onToken: (text) => patchLast((m) => ({ ...m, text: m.text + text })),
          onDone: ({ warnings, followups: fu, blocked }) => {
            patchLast({ warnings, blocked, streaming: false });
            setFollowups(fu ?? []);
          },
        },
      );
    } catch (err) {
      patchLast({
        role: 'assistant', error: true, streaming: false,
        text: err.error ?? 'Something went wrong.', message: err.message ?? '',
      });
    } finally {
      // An aborted stream never reaches onDone, so the streaming flag has to be cleared here as
      // well — otherwise the cursor blinks forever on a message that stopped growing.
      patchLast((m) => (m.streaming ? { ...m, streaming: false, stopped: true } : m));
      setLoading(false);
      abortRef.current = null;
    }
  }, [loading, messages, hrm]);

  const stop = useCallback(() => abortRef.current?.abort(), []);

  const resetChat = useCallback(() => {
    abortRef.current?.abort();
    setMessages([]);
    setFollowups([]);
    setSources([]);
    citationsRef.current = [];   // a new conversation renumbers citations from [1]
  }, []);

  // A new (or cleared) melt file invalidates the conversation about the old one: its numbers,
  // its citations and its follow-ups all referred to data that no longer exists.
  const setHrm = useCallback((v) => {
    setHrmState(v);
    resetChat();
  }, [resetChat]);

  const clearHrm = useCallback(() => {
    setHrmState(null);
    resetChat();
  }, [resetChat]);

  const value = useMemo(
    () => ({
      hrm, setHrm, clearHrm,
      sessionId: hrm?.session_id ?? null,
      hasHrm: Boolean(hrm),

      messages, loading, followups, sources,
      send, stop, resetChat,
    }),
    [hrm, setHrm, clearHrm, messages, loading, followups, sources, send, stop, resetChat],
  );

  return <HrmSessionContext.Provider value={value}>{children}</HrmSessionContext.Provider>;
}

export function useHrmSession() {
  const ctx = useContext(HrmSessionContext);
  if (!ctx) throw new Error('useHrmSession must be used inside <HrmSessionProvider>');
  return ctx;
}
