import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import ChatPanel from './ChatPanel.jsx';
import { fetchChatHealth } from '../api/chatApi.js';
import { useHrmSession } from '../contexts/HrmSessionContext.jsx';

/**
 * ChatbotPanel — the always-present sidebar assistant.
 *
 * This was a "coming soon" stub with a disabled input. It is now the real Phase 1
 * assistant: same backend, same guardrails, same HRM session as the /assistant page — it
 * just renders ChatPanel in compact mode rather than duplicating the chat logic, so the two
 * surfaces can never drift apart in behaviour.
 *
 * The panel is only useful once Ollama is up, so when it is not, the panel says exactly
 * what is missing and how to fix it instead of failing on the first question.
 */

const AIAvatar = ({ size = 'md' }) => {
  const sizeMap = { sm: 'w-5 h-5', md: 'w-8 h-8', lg: 'w-14 h-14' };
  const ringMap = { sm: 'ring-1', md: 'ring-2', lg: 'ring-2' };
  return (
    <img
      src="/HuynhLuanAI.jpg"
      alt="HuynhLuanAI"
      className={`${sizeMap[size]} ${ringMap[size]} ring-pink-300 ring-offset-1 rounded-full object-cover object-top shrink-0`}
    />
  );
};

export default function ChatbotPanel() {
  const [isOpen, setIsOpen] = useState(false);
  const [health, setHealth] = useState(null);
  const { hasHrm, loading, messages } = useHrmSession();

  // Probed only when the panel is first opened — /api/health on every page load would cost
  // a request the collapsed panel has no use for.
  useEffect(() => {
    if (isOpen && health === null) {
      fetchChatHealth()
        .then(setHealth)
        .catch(() => setHealth({ ready: false, unreachable: true }));
    }
  }, [isOpen, health]);

  return (
    <aside
      className={`hidden lg:flex flex-col bg-white shrink-0 border-l border-gray-100
        transition-[width] duration-300 ease-in-out overflow-hidden
        ${isOpen ? 'w-96' : 'w-16'}`}
    >
      {/* ── Toggle / header ── */}
      {isOpen ? (
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100 shrink-0">
          <div className="flex items-center gap-2 min-w-0">
            <AIAvatar size="sm" />
            <span className="text-sm font-semibold text-gray-700 truncate">HuynhLuanAI</span>
            {hasHrm && (
              <span className="text-[9px] font-bold text-teal-700 bg-teal-50 border border-teal-200 px-1.5 py-0.5 rounded-full leading-none shrink-0">
                HRM
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={() => setIsOpen(false)}
            title="Collapse"
            className="w-6 h-6 flex items-center justify-center rounded text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors text-xs font-bold shrink-0"
          >
            ✕
          </button>
        </div>
      ) : (
        <div className="flex justify-center pt-5 shrink-0">
          <button
            type="button"
            onClick={() => setIsOpen(true)}
            title={loading
              ? 'The assistant is writing an answer — click to watch'
              : 'Open HuynhLuanAI Assistant'}
            className="relative flex flex-col items-center gap-1.5 px-2 py-2.5 rounded-2xl bg-pink-50 border border-pink-200
              hover:bg-pink-100 hover:border-pink-300 hover:shadow-md transition-all duration-150 active:scale-95 group"
          >
            <AIAvatar size="md" />
            <span className="text-[9px] font-bold text-pink-700 leading-tight group-hover:text-pink-800">
              HuynhLuanAI
            </span>

            {/* An answer takes minutes. The user is free to walk to another page while it runs,
                so the collapsed panel has to show that something is still happening — otherwise
                the answer lands silently in a panel they are not looking at. */}
            {loading ? (
              <span className="absolute top-1 right-1 flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-teal-500" />
              </span>
            ) : messages.length > 0 && (
              <span className="absolute top-1 right-1 h-2.5 w-2.5 rounded-full bg-teal-500 border border-white" />
            )}
          </button>
        </div>
      )}

      {/* ── Panel content ── */}
      <div
        className={`flex flex-col flex-1 min-h-0 overflow-hidden transition-opacity duration-200 delay-100 ${
          isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'
        }`}
      >
        {health && !health.ready ? (
          <NotReady health={health} />
        ) : (
          <>
            <ChatPanel compact />
            <p className="px-3 pb-2 text-[10px] text-gray-300 text-center leading-snug shrink-0">
              Explains results only — it never designs primers.{' '}
              <Link to="/assistant" className="text-gray-400 hover:text-teal-700 underline">
                Upload HRM data
              </Link>
            </p>
          </>
        )}
      </div>
    </aside>
  );
}

/**
 * Ollama must be installed and the model pulled before the assistant can answer, and that is
 * a step only the user can take. Name the missing piece and the exact command — a bare
 * "unavailable" would leave them guessing.
 */
function NotReady({ health }) {
  const problems = [];

  if (health.unreachable) {
    problems.push({
      what: 'The backend is not reachable',
      how:  'Start Flask:  cd backend && python app.py',
    });
  } else if (!health.ollama?.alive) {
    problems.push({
      what: 'Ollama is not running',
      how:  'Install from ollama.com/download, then start it.',
    });
  } else if (!health.ollama?.model_ready) {
    problems.push({
      what: `Model "${health.ollama.model}" is not pulled`,
      how:  `ollama pull ${health.ollama.model}`,
    });
  }

  if (health.chroma && !health.chroma.alive) {
    problems.push({ what: 'Vector store unavailable', how: 'pip install chromadb' });
  }

  return (
    <div className="flex flex-col items-center text-center px-5 py-8 space-y-3">
      <AIAvatar size="lg" />
      <p className="text-xs font-semibold text-gray-700">Assistant not ready</p>
      <ul className="space-y-2 w-full">
        {problems.map((p) => (
          <li key={p.what} className="text-left border border-amber-200 bg-amber-50 rounded-lg px-2.5 py-2">
            <p className="text-[11px] font-medium text-amber-800 leading-snug">{p.what}</p>
            <code className="block mt-1 text-[10px] text-amber-900 bg-amber-100 px-1.5 py-1 rounded break-all">
              {p.how}
            </code>
          </li>
        ))}
      </ul>
    </div>
  );
}
