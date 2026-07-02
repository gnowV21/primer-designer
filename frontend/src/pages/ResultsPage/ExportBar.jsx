// ExportBar — Download PDF / Download CSV buttons (Phase 4 §8.6).
// Calls POST /api/export with results blob, triggers browser download.

import { useState } from 'react';
import axios from 'axios';

function filenameFromDisposition(cd, fallback) {
  if (!cd) return fallback;
  const match = cd.match(/filename=([^;"\s]+|"[^"]*")/i);
  if (!match) return fallback;
  return match[1].replace(/^"|"$/g, '');
}

export default function ExportBar({ results }) {
  const [pdfState, setPdfState] = useState('idle'); // idle | busy | error
  const [csvState, setCsvState] = useState('idle');
  const [pdfErr, setPdfErr] = useState(null);
  const [csvErr, setCsvErr] = useState(null);

  async function download(format) {
    const setS = format === 'pdf' ? setPdfState : setCsvState;
    const setE = format === 'pdf' ? setPdfErr   : setCsvErr;
    setS('busy');
    setE(null);
    try {
      const resp = await axios.post(
        '/api/export',
        { format, results },
        { responseType: 'blob', timeout: 30000 },
      );
      const cd = resp.headers['content-disposition'] ?? '';
      const filename = filenameFromDisposition(cd, format === 'pdf' ? 'primer_report.pdf' : 'primers.csv');
      const url = URL.createObjectURL(resp.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setS('idle');
    } catch (err) {
      const status = err.response?.status;
      let msg = 'Export failed.';
      if (status === 503) msg = 'PDF export unavailable (reportlab not installed on server).';
      else if (status === 400) msg = 'Export request invalid.';
      else if (err.code === 'ECONNABORTED') msg = 'Export timed out.';
      setE(msg);
      setS('error');
    }
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 space-y-2">
      <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Export</p>
      <div className="flex flex-wrap gap-2 items-center">
        <ExportButton
          label="Download PDF"
          busy={pdfState === 'busy'}
          onClick={() => download('pdf')}
          icon="⬇"
        />
        <ExportButton
          label="Download CSV"
          busy={csvState === 'busy'}
          onClick={() => download('csv')}
          icon="⬇"
          secondary
        />
      </div>
      {pdfErr && <p className="text-xs text-red-700">{pdfErr}</p>}
      {csvErr && <p className="text-xs text-red-700">{csvErr}</p>}
      <p className="text-xs text-slate-400">
        CSV: MIQE-aligned columns, Excel-compatible UTF-8.
        PDF: includes comparison table + quality summary.
      </p>
    </div>
  );
}

function ExportButton({ label, busy, onClick, icon, secondary }) {
  return (
    <button
      onClick={onClick}
      disabled={busy}
      className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold transition
        ${busy ? 'opacity-50 cursor-not-allowed' : 'hover:opacity-90 active:scale-[0.98]'}
        ${secondary
          ? 'bg-slate-100 text-slate-700 border border-slate-200'
          : 'bg-teal-600 text-white shadow-sm'
        }`}
    >
      {busy
        ? <span className="animate-spin">⟳</span>
        : <span className="text-base leading-none">{icon}</span>
      }
      {busy ? 'Generating…' : label}
    </button>
  );
}
