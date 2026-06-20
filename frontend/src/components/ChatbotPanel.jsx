import { useState } from 'react';

const RobotIcon = ({ className }) => (
  <svg viewBox="0 0 20 20" fill="none" className={className} aria-hidden="true">
    <rect x="3" y="7" width="14" height="10" rx="2" stroke="currentColor" strokeWidth="1.5"/>
    <rect x="7" y="10" width="2" height="2" rx="0.5" fill="currentColor"/>
    <rect x="11" y="10" width="2" height="2" rx="0.5" fill="currentColor"/>
    <line x1="7" y1="15" x2="13" y2="15" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    <line x1="10" y1="7" x2="10" y2="4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    <circle cx="10" cy="3" r="1" fill="currentColor"/>
    <line x1="3" y1="11" x2="1" y2="11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    <line x1="17" y1="11" x2="19" y2="11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
  </svg>
);

const SparkleIcon = ({ className }) => (
  <svg viewBox="0 0 16 16" fill="currentColor" className={className} aria-hidden="true">
    <path d="M8 1l1.5 4.5L14 7l-4.5 1.5L8 13l-1.5-4.5L2 7l4.5-1.5z"/>
  </svg>
);

const PREVIEW_CAPABILITIES = [
  { icon: '🔬', text: 'Explain thermodynamic parameters' },
  { icon: '⚗️',  text: 'Interpret primer quality scores'  },
  { icon: '📊', text: 'Suggest optimizations for your sample type' },
  { icon: '📚', text: 'Answer questions about miRNA RT-qPCR protocol' },
];

export default function ChatbotPanel() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <aside
      className={`hidden lg:flex flex-col bg-white shrink-0
        transition-[width] duration-300 ease-in-out overflow-hidden
        ${isOpen ? 'w-80' : 'w-16'}`}
    >
      {/* ── Toggle / header ── */}
      {isOpen ? (
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100 shrink-0">
          <div className="flex items-center gap-2">
            <RobotIcon className="w-4 h-4 text-teal-600 shrink-0" />
            <span className="text-sm font-semibold text-gray-700">AI Assistant</span>
            <span className="text-[10px] font-bold text-teal-600 bg-teal-50 border border-teal-200 px-1.5 py-0.5 rounded-full leading-none">
              SOON
            </span>
          </div>
          <button
            type="button"
            onClick={() => setIsOpen(false)}
            title="Collapse"
            className="w-6 h-6 flex items-center justify-center rounded text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors text-xs font-bold"
          >
            ✕
          </button>
        </div>
      ) : (
        <div className="flex justify-center pt-5 shrink-0">
          <button
            type="button"
            onClick={() => setIsOpen(true)}
            title="Open AI Assistant"
            className="flex flex-col items-center gap-1.5 px-2.5 py-3 rounded-2xl bg-teal-50 border border-teal-200
              hover:bg-teal-100 hover:border-teal-300 transition-all duration-150 active:scale-95"
          >
            <RobotIcon className="w-5 h-5 text-teal-600" />
            <span className="text-[9px] font-bold text-teal-700 leading-tight">AI</span>
          </button>
        </div>
      )}

      {/* ── Panel content ── */}
      <div
        className={`flex flex-col flex-1 overflow-hidden transition-opacity duration-200 delay-100 ${
          isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'
        }`}
      >
        {/* Coming-soon hero */}
        <div className="flex flex-col items-center text-center px-5 py-6 space-y-3 border-b border-gray-100">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-teal-50 to-teal-100 border border-teal-200 flex items-center justify-center shadow-sm">
            <RobotIcon className="w-6 h-6 text-teal-600" />
          </div>
          <div className="space-y-1">
            <p className="text-sm font-semibold text-gray-700">AI Assistant</p>
            <p className="text-xs text-gray-400 leading-relaxed">
              An AI layer that helps you understand and refine your primer design results.
            </p>
          </div>
          <span className="inline-flex items-center gap-1 text-[10px] font-bold text-teal-600 bg-teal-50 border border-teal-200 px-2.5 py-1 rounded-full">
            <SparkleIcon className="w-2.5 h-2.5" />
            In development
          </span>
        </div>

        {/* Planned capabilities */}
        <div className="px-4 py-4 space-y-2 flex-1">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 mb-3">
            Planned capabilities
          </p>
          {PREVIEW_CAPABILITIES.map(({ icon, text }) => (
            <div
              key={text}
              className="flex items-start gap-2.5 px-3 py-2 rounded-lg bg-gray-50 border border-gray-100"
            >
              <span className="text-sm leading-none mt-0.5">{icon}</span>
              <span className="text-xs text-gray-500 leading-snug">{text}</span>
            </div>
          ))}
        </div>

        {/* Disabled input */}
        <div className="px-4 py-3 border-t border-gray-100 shrink-0">
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Ask about your primers…"
              disabled
              className="flex-1 text-xs border border-gray-200 rounded-lg px-2.5 py-2 bg-gray-50 text-gray-400 placeholder-gray-300 cursor-not-allowed"
            />
            <button
              disabled
              className="px-3 py-2 rounded-lg bg-gray-100 text-gray-300 text-xs cursor-not-allowed font-semibold"
            >
              Send
            </button>
          </div>
          <p className="text-[10px] text-gray-300 text-center mt-2">
            Available after primer design engine is complete
          </p>
        </div>
      </div>
    </aside>
  );
}
