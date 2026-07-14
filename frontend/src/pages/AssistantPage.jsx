import { useEffect, useState } from 'react';
import ChatPanel from '../components/ChatPanel.jsx';
import HRMChart from '../components/HRMChart.jsx';
import HRMUpload from '../components/HRMUpload.jsx';
import KnowledgeBase from '../components/KnowledgeBase.jsx';
import SourcesPanel from '../components/SourcesPanel.jsx';
import { fetchChatHealth } from '../api/chatApi.js';
import { useHrmSession } from '../contexts/HrmSessionContext.jsx';

/**
 * AssistantPage — the Phase 1 chatbot [SPEC_Phase1 §7 frontend].
 *
 * Left column  : the evidence — knowledge base, HRM numbers, melt curves.
 * Right column : the conversation grounded in that evidence, plus its sources.
 *
 * The layout is the argument: the numbers the model is allowed to quote sit next to
 * the answer that quotes them, so a fabricated figure is visible at a glance.
 */
export default function AssistantPage() {
  // Everything session-scoped lives in context, not local state: the sidebar assistant shows the
  // same upload and the same conversation, and neither may be destroyed by navigating away.
  const { hrm, setHrm, clearHrm, sources } = useHrmSession();
  const [health, setHealth] = useState(null);

  useEffect(() => {
    fetchChatHealth().then(setHealth).catch(() => setHealth(null));
  }, []);

  return (
    <div className="max-w-7xl mx-auto space-y-4">
      <header>
        <h1 className="text-lg font-bold text-slate-800">Result Assistant</h1>
        <p className="text-xs text-gray-500 mt-0.5">
          Explains stem-loop RT-qPCR / HRM results using your ingested papers and the
          numeric table computed from your melt-curve file. It never invents numbers
          and never designs primers.
        </p>
      </header>

      {health && !health.ready && <SetupBanner health={health} />}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 items-start">
        {/* Evidence */}
        <div className="space-y-5">
          <KnowledgeBase />
          <HRMUpload result={hrm} onResult={setHrm} onClear={clearHrm} />
          {hrm && <HRMChart curves={hrm.curves} features={hrm.features} />}
        </div>

        {/* Conversation */}
        <div className="space-y-4 lg:sticky lg:top-4">
          <div className="h-[520px]">
            <ChatPanel />
          </div>
          <SourcesPanel sources={sources} />
        </div>
      </div>
    </div>
  );
}

/**
 * The assistant is useless until Ollama is installed and the model is pulled, and
 * that is a step the user must run themselves. Say exactly which piece is missing
 * and exactly what to type — a generic "service unavailable" would strand them.
 */
function SetupBanner({ health }) {
  const problems = [];

  if (!health.ollama?.alive) {
    problems.push({
      what: 'Ollama is not running',
      how:  'Install it from ollama.com/download, then start it.',
    });
  } else if (!health.ollama?.model_ready) {
    problems.push({
      what: `The model "${health.ollama.model}" is not pulled`,
      how:  `Run:  ollama pull ${health.ollama.model}`,
    });
  }

  if (health.embedder && !health.embedder.installed) {
    problems.push({
      what: 'sentence-transformers is not installed',
      how:  'Run:  pip install sentence-transformers',
    });
  }

  if (!health.chroma?.alive) {
    problems.push({
      what: 'The vector store is unavailable',
      how:  health.chroma?.error || 'Run:  pip install chromadb',
    });
  }

  if (problems.length === 0) return null;

  return (
    <div className="border border-amber-200 bg-amber-50 rounded-xl px-4 py-3">
      <p className="text-xs font-semibold text-amber-800">
        Setup incomplete — the assistant cannot answer yet.
      </p>
      <ul className="mt-2 space-y-1.5">
        {problems.map((p) => (
          <li key={p.what} className="text-[11px] text-amber-700 leading-snug">
            <span className="font-medium">{p.what}.</span>{' '}
            <code className="text-amber-900 bg-amber-100 px-1 py-0.5 rounded">{p.how}</code>
          </li>
        ))}
      </ul>
    </div>
  );
}
