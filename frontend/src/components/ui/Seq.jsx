// Sequences on screen (UI review 2026-11-23): a sequence is never broken across lines.
//   <Seq>        short sequence (≤ 30 nt), accession or range — mono, nowrap (.seq)
//   <SeqBlock>   long sequence (the 50-nt RT primer) — one line that scrolls inside its
//                box (.seq-block), 5′-…-3′ notation, with a copy button next to it
//   <CopyButton> the copy button alone, for a sequence shown elsewhere
import { useState } from 'react';

export function Seq({ children, className = '', ...rest }) {
  return <span className={`seq ${className}`} {...rest}>{children}</span>;
}

export function CopyButton({ text, label = 'Copy', title, className = '' }) {
  const [copied, setCopied] = useState(false);
  function copy() {
    navigator.clipboard?.writeText(text ?? '').then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }).catch(() => {});
  }
  return (
    <button
      type="button"
      onClick={copy}
      title={title || `Copy ${text ?? ''}`}
      aria-label={title || 'Copy sequence'}
      className={`shrink-0 text-xs font-medium px-2 py-0.5 rounded border border-slate-300 bg-white text-slate-700 hover:bg-slate-100 transition ${className}`}
    >
      {copied ? 'Copied' : label}
    </button>
  );
}

/** 5′-SEQ-3′ on one line (scrolls sideways when the box is narrower) + Copy. */
export function SeqBlock({ sequence, className = '', textClass = 'text-xs text-slate-800', copy = true, testId }) {
  if (!sequence) return null;
  return (
    <div className={`flex items-center gap-2 min-w-0 ${className}`} data-testid={testId}>
      <code className={`seq-block flex-1 min-w-0 leading-relaxed py-0.5 ${textClass}`}>
        5′-{sequence}-3′
      </code>
      {copy && <CopyButton text={sequence} />}
    </div>
  );
}
