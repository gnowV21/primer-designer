import { useState } from 'react';

const AIAvatar = ({ size = 'md' }) => {
  const sizeMap = {
    sm: 'w-5 h-5',
    md: 'w-8 h-8',
    lg: 'w-14 h-14',
  };
  const ringMap = {
    sm: 'ring-1',
    md: 'ring-2',
    lg: 'ring-2',
  };
  return (
    <img
      src="/HuynhLuanAI.jpg"
      alt="HuynhLuanAI"
      className={`${sizeMap[size]} ${ringMap[size]} ring-pink-300 ring-offset-1 rounded-full object-cover object-top shrink-0`}
    />
  );
};


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
            <AIAvatar size="sm" />
            <span className="text-sm font-semibold text-gray-700">LuanHuynhAI Assistant</span>
            <span className="text-[10px] font-bold text-pink-600 bg-pink-50 border border-pink-200 px-1.5 py-0.5 rounded-full leading-none">
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
            title="Open HuynhLuanAI Assistant"
            className="flex flex-col items-center gap-1.5 px-2 py-2.5 rounded-2xl bg-pink-50 border border-pink-200
              hover:bg-pink-100 hover:border-pink-300 hover:shadow-md transition-all duration-150 active:scale-95 group"
          >
            <AIAvatar size="md" />
            <span className="text-[9px] font-bold text-pink-700 leading-tight group-hover:text-pink-800">HuynhLuanAI</span>
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
          <div className="relative">
            <AIAvatar size="lg" />
            <span className="absolute -bottom-1 -right-1 w-4 h-4 bg-pink-500 rounded-full border-2 border-white flex items-center justify-center">
              <svg viewBox="0 0 8 8" fill="white" className="w-2 h-2"><path d="M4 1l.7 2.1H7l-1.9 1.4.7 2.1L4 5.2 2.2 6.6l.7-2.1L1 3.1h2.3z"/></svg>
            </span>
          </div>
          <div className="space-y-1">
            <p className="text-sm font-semibold text-gray-700">LuanHuynhAI Assistant</p>
            <p className="text-xs text-gray-400 leading-relaxed">
              If u have any questions, contact Dr.LuanHuynh,pls.
            </p>
          </div>
          <span className="inline-flex items-center gap-1 text-[10px] font-bold text-pink-600 bg-pink-50 border border-pink-200 px-2.5 py-1 rounded-full">
            ✨ In development
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
