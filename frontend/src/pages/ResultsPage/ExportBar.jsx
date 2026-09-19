// ExportBar — Download PDF / CSV / FASTA buttons (Phase 4 §8.6).
// Calls POST /api/export with the results (and the BLAST result, if the
// off-target check was run) as a blob, then triggers a browser download.

import { useState } from 'react';
import axios from 'axios';
import { listDesigns } from '../../utils/historyDb.js';

function filenameFromDisposition(cd, fallback) {
  if (!cd) return fallback;
  const match = cd.match(/filename=([^;"\s]+|"[^"]*")/i);
  if (!match) return fallback;
  return match[1].replace(/^"|"$/g, '');
}

const FALLBACK_NAME = {
  pdf:   'primer_report.pdf',
  csv:   'primers.csv',
  fasta: 'primer_order.fasta',
};

export default function ExportBar({ results, blastResult }) {
  const [busyFmt, setBusyFmt] = useState(null); // 'pdf' | 'csv' | 'fasta' | null
  const [error, setError]     = useState(null);

  async function download(format) {
    setBusyFmt(format);
    setError(null);
    try {
      // Earlier designs of this miRNA in this browser (minus the current one) —
      // shown in the PDF as an amplicon carry-over reminder.
      const mirnaId = results?.metadata?.mirna_id;
      const history_count = mirnaId
        ? Math.max(0, (await listDesigns()).filter((d) => d.mirnaId === mirnaId).length - 1)
        : 0;
      const resp = await axios.post(
        '/api/export',
        { format, results, blast_result: blastResult ?? null, history_count },
        { responseType: 'blob', timeout: 30000 },
      );
      const cd = resp.headers['content-disposition'] ?? '';
      const filename = filenameFromDisposition(cd, FALLBACK_NAME[format] ?? 'export.txt');
      const url = URL.createObjectURL(resp.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setBusyFmt(null);
    } catch (err) {
      const status = err.response?.status;
      let msg = 'Export failed.';
      if (status === 503) msg = 'PDF export unavailable (reportlab not installed on server).';
      else if (status === 400) msg = 'Export request invalid.';
      else if (err.code === 'ECONNABORTED') msg = 'Export timed out.';
      setError(msg);
      setBusyFmt(null);
    }
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 space-y-2">
      <p className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Export</p>
      <div className="flex flex-wrap gap-2 items-center">
        <ExportButton label="Download PDF"   busy={busyFmt === 'pdf'}   onClick={() => download('pdf')}   icon="⬇" />
        <ExportButton label="Download CSV"   busy={busyFmt === 'csv'}   onClick={() => download('csv')}   icon="⬇" secondary />
        <ExportButton label="FASTA (order)"  busy={busyFmt === 'fasta'} onClick={() => download('fasta')} icon="⬇" secondary />
      </div>
      {error && <p className="text-sm text-red-700">{error}</p>}
      <p className="text-xs text-slate-500 leading-relaxed">
        PDF: full report (comparison, scientific notes, off-target, MIQE checklist).
        CSV: Excel-compatible data + specificity + checklist. FASTA: synthesis-order-ready.
        {!blastResult && (
          <span className="text-amber-600"> Run the Off-target (BLAST) check above to include it in the report.</span>
        )}
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
