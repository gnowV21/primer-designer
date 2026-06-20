// Scientific SVG icons for the three stem-loop RT-qPCR primer types.
// Exported individually so any page (results, legend, etc.) can import what it needs.

export function StemLoopIcon({ className }) {
  return (
    <svg viewBox="0 0 30 32" fill="none" className={className} aria-hidden="true">
      {/* Left arm of stem */}
      <line x1="7" y1="28" x2="7" y2="17" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
      {/* Right arm of stem */}
      <line x1="13" y1="28" x2="13" y2="17" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
      {/* Loop (semicircle at top) */}
      <path d="M7 17 C7 9 13 9 13 17" stroke="currentColor" strokeWidth="2.5" fill="none" strokeLinecap="round"/>
      {/* Base-pair dashes in stem region */}
      <line x1="7" y1="20" x2="13" y2="20" stroke="currentColor" strokeWidth="1.5" strokeDasharray="1.5 2" opacity="0.45"/>
      <line x1="7" y1="24" x2="13" y2="24" stroke="currentColor" strokeWidth="1.5" strokeDasharray="1.5 2" opacity="0.45"/>
      {/* 3' overhang extending right */}
      <line x1="13" y1="28" x2="25" y2="28" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
      {/* Arrowhead on 3' overhang */}
      <polyline points="22,25 25,28 22,31" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

export function ForwardPrimerIcon({ className }) {
  return (
    <svg viewBox="0 0 28 22" fill="none" className={className} aria-hidden="true">
      {/* Primer body */}
      <line x1="2" y1="11" x2="20" y2="11" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
      {/* Arrowhead */}
      <path d="M16 6 L22 11 L16 16" stroke="currentColor" strokeWidth="2.5" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
      {/* Nucleotide tick marks (miRNA-specific region) */}
      <line x1="5" y1="8" x2="5" y2="14" stroke="currentColor" strokeWidth="1.5" opacity="0.35" strokeLinecap="round"/>
      <line x1="9" y1="8" x2="9" y2="14" stroke="currentColor" strokeWidth="1.5" opacity="0.35" strokeLinecap="round"/>
      <line x1="13" y1="8" x2="13" y2="14" stroke="currentColor" strokeWidth="1.5" opacity="0.35" strokeLinecap="round"/>
    </svg>
  );
}

export function PadlockIcon({ className }) {
  return (
    <svg viewBox="0 0 24 26" fill="none" className={className} aria-hidden="true">
      {/* Lock body */}
      <rect x="3" y="12" width="18" height="12" rx="2.5" stroke="currentColor" strokeWidth="2.5"/>
      {/* Shackle */}
      <path d="M7 12 V9 C7 5.5 17 5.5 17 9 V12" stroke="currentColor" strokeWidth="2.5" fill="none" strokeLinecap="round"/>
      {/* Keyhole */}
      <circle cx="12" cy="18" r="2" stroke="currentColor" strokeWidth="2"/>
      <line x1="12" y1="20" x2="12" y2="22.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  );
}
