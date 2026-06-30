// ScoreGauge — circular arc gauge showing total score 0–100 with grade label.

export default function ScoreGauge({ score, grade, compact = false }) {
  const pct  = Math.min(100, Math.max(0, score));
  const size = compact ? 52 : 80;
  const sw   = compact ? 5 : 7;
  const r    = (size - sw) / 2;
  const circ = 2 * Math.PI * r;
  const arc  = circ * 0.75; // 270° sweep
  const fill = arc * (pct / 100);

  const colors = {
    Excellent:  '#0d9488',
    Good:       '#2563eb',
    Acceptable: '#d97706',
    Poor:       '#dc2626',
  };
  const stroke = colors[grade] ?? '#94a3b8';

  return (
    <div className={`flex flex-col items-center gap-0.5 ${compact ? '' : 'py-1'}`}>
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        style={{ transform: 'rotate(135deg)' }}
      >
        {/* Track */}
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none" stroke="#e2e8f0" strokeWidth={sw}
          strokeDasharray={`${arc} ${circ}`}
          strokeLinecap="round"
        />
        {/* Fill */}
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none" stroke={stroke} strokeWidth={sw}
          strokeDasharray={`${fill} ${circ}`}
          strokeLinecap="round"
          style={{ transition: 'stroke-dasharray 0.6s ease' }}
        />
      </svg>
      {compact ? (
        <span className="text-xs font-bold tabular-nums" style={{ color: stroke, marginTop: '-6px' }}>
          {pct.toFixed(0)}
        </span>
      ) : (
        <div className="text-center -mt-3 space-y-0.5">
          <p className="text-2xl font-bold tabular-nums" style={{ color: stroke }}>{pct.toFixed(1)}</p>
          <p className="text-xs text-gray-400">/ 100</p>
          <p className="text-xs font-semibold" style={{ color: stroke }}>{grade}</p>
        </div>
      )}
    </div>
  );
}
