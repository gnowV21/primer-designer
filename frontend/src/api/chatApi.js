import axios from 'axios';

/**
 * chatApi.js — the four Phase 1 endpoints [SPEC_Phase1 §6].
 *
 * Every call is relative to /api, which Vite proxies to Flask on :5000 in dev.
 * Errors are normalized to `{ error, message }` so every caller can render a
 * failure the same way instead of reaching into axios internals.
 */

// CPU inference on the 7B model runs 2-4 minutes on a 16 GB machine with no GPU, and the first
// call also pays a one-off embedding-model load. The browser must not give up before the
// backend has had a fair chance to answer.
const CHAT_TIMEOUT_MS = 600_000;

// The first ingest downloads S-PubMedBert (~440 MB) before it can embed anything.
const INGEST_TIMEOUT_MS = 600_000;

const HRM_TIMEOUT_MS = 60_000;

function normalizeError(err) {
  const data = err?.response?.data;
  if (data?.error) {
    return { error: data.error, message: data.message || '' };
  }
  if (err.code === 'ECONNABORTED') {
    return {
      error: 'Request timed out.',
      message: 'The backend did not answer in time. The model runs on CPU and is slow — try a shorter question.',
    };
  }
  return {
    error: 'Cannot reach the backend.',
    message: 'Check that the Flask server is running on port 5000.',
  };
}

/** GET /api/chat/health — readiness of Ollama, the embedder, Chroma and SQLite. */
export async function fetchChatHealth() {
  try {
    const { data } = await axios.get('/api/chat/health', { timeout: 8000 });
    return data;
  } catch (err) {
    throw normalizeError(err);
  }
}

/** POST /api/chat — question (+ history + optional HRM session) -> grounded answer. */
export async function askQuestion({ question, sessionId, history = [] }) {
  try {
    const { data } = await axios.post(
      '/api/chat',
      { question, session_id: sessionId || '', history },
      { timeout: CHAT_TIMEOUT_MS },
    );
    return data;
  } catch (err) {
    throw normalizeError(err);
  }
}

/**
 * POST /api/chat/stream — the same answer, delivered token by token over SSE.
 *
 * fetch, not axios: XHR only exposes the response body once it is complete, which would
 * defeat the entire point. AbortController is what makes the Stop button real — without it
 * "stop" could only hide the answer, while the server kept generating it.
 *
 * Callbacks: onMeta({sources, usedHrm}), onToken(text), onDone({warnings, followups, blocked}).
 * Rejects with {error, message} on failure. An abort resolves quietly — a user who pressed
 * Stop does not need to be told about an error they caused on purpose.
 */
export async function askQuestionStream(
  { question, sessionId, history = [], citations = [], signal },
  { onMeta, onToken, onDone } = {},
) {
  let res;
  try {
    res = await fetch('/api/chat/stream', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      // `citations` is the accumulated [{n, pmid}] registry. Sending it back is what keeps a
      // paper's number the same across turns, so the "[1]" in an earlier answer still points
      // at the paper it pointed at when it was written.
      body:    JSON.stringify({ question, session_id: sessionId || '', history, citations }),
      signal,
    });
  } catch (err) {
    if (err.name === 'AbortError') return;
    throw { error: 'Cannot reach the backend.',
            message: 'Check that the Flask server is running on port 5000.' };
  }

  if (!res.ok) {
    let body = {};
    try { body = await res.json(); } catch { /* non-JSON error body */ }
    throw {
      error:   body.error || `Backend returned HTTP ${res.status}.`,
      message: body.message || '',
    };
  }

  const reader  = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // SSE frames are separated by a blank line. A frame can arrive split across chunks, so
      // only whole frames are consumed and the remainder is carried over.
      const frames = buffer.split('\n\n');
      buffer = frames.pop() ?? '';

      for (const frame of frames) {
        const evMatch   = frame.match(/^event:\s*(.+)$/m);
        const dataMatch = frame.match(/^data:\s*(.+)$/m);
        if (!evMatch || !dataMatch) continue;

        let payload;
        try { payload = JSON.parse(dataMatch[1]); } catch { continue; }

        switch (evMatch[1].trim()) {
          case 'meta':
            onMeta?.({
              sources:   payload.sources ?? [],
              citations: payload.citations ?? [],
              usedHrm:   payload.used_hrm,
            });
            break;
          case 'token':
            onToken?.(payload.text ?? '');
            break;
          case 'done':
            onDone?.({
              warnings:  payload.warnings ?? [],
              followups: payload.followups ?? [],
              blocked:   payload.blocked,
            });
            break;
          case 'error':
            throw { error: payload.error, message: payload.message };
          default:
            break;
        }
      }
    }
  } catch (err) {
    if (err?.name === 'AbortError' || signal?.aborted) return;   // user pressed Stop
    throw err;
  }
}

/** POST /api/hrm/analyze — melt-curve file -> numeric table + curves + session id. */
export async function analyzeHrm(file, { tPre, tPost, positiveControl } = {}) {
  const form = new FormData();
  form.append('file', file);
  if (tPre !== undefined && tPre !== '') form.append('T_pre', tPre);
  if (tPost !== undefined && tPost !== '') form.append('T_post', tPost);
  if (positiveControl) form.append('positive_control', positiveControl);

  try {
    const { data } = await axios.post('/api/hrm/analyze', form, { timeout: HRM_TIMEOUT_MS });
    return data;
  } catch (err) {
    throw normalizeError(err);
  }
}

/** POST /api/ingest — PubMed keyword search -> papers stored + chunks embedded. */
export async function ingestPapers({ query, maxResults = 20 }) {
  try {
    const { data } = await axios.post(
      '/api/ingest',
      { query, max_results: maxResults },
      { timeout: INGEST_TIMEOUT_MS },
    );
    return data;
  } catch (err) {
    throw normalizeError(err);
  }
}

/** GET /api/papers — what is currently in the knowledge base. */
export async function fetchPapers({ page = 1, perPage = 20 } = {}) {
  try {
    const { data } = await axios.get('/api/papers', {
      params: { page, per_page: perPage },
      timeout: 15_000,
    });
    return data;
  } catch (err) {
    throw normalizeError(err);
  }
}
