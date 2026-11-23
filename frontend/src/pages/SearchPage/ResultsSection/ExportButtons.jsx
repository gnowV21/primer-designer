// ExportButtons — copy primers to clipboard in various formats.

import { useState } from 'react';
import { hasTiers } from '../../../utils/tierRank.js';

export default function ExportButtons({ set, stemloop, reverse }) {
  const [copied, setCopied] = useState('');

  function copy(text, label) {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(label);
      setTimeout(() => setCopied(''), 2000);
    });
  }

  const tiered = hasTiers(set);

  function tsvRow() {
    if (tiered) {
      // Tiered (4.0.0): the V4 "Score" column is the tie-break score; group totals added.
      const r = set.ranking;
      const cols = [
        `#${set.rank} Forward`, set.sequence, stemloop?.sequence ?? '', reverse?.sequence ?? '',
        set.grade ?? '', `${r.specificity.total}/${r.specificity.max}`, `${r.pcr.total}/${r.pcr.max}`,
        `${r.flexible.total}/${r.flexible.max}`, r.detailed_score?.toFixed(1) ?? '',
        set.tm_full?.toFixed(1) ?? '', set.gc_percent ?? '', set.amplicon_size ?? '',
      ];
      return [
        // Column titles follow the criteria groups (2026-11-22, same names as the CSV
        // export); values and column order unchanged.
        ['Rank', 'Forward Primer', 'RT Primer', 'Reverse Primer', 'Grade', 'Req_S_total', 'Flex2_PCR',
          'Flex3_composition_structure',
          'Tie-break score', 'Tm (°C)', 'GC%', 'Amplicon (bp)'].join('\t'),
        cols.join('\t'),
      ].join('\n');
    }
    const cols = [
      `#${set.rank} Forward`,
      set.sequence,
      stemloop?.sequence ?? '',
      reverse?.sequence  ?? '',
      set.total_score?.toFixed(1) ?? '',
      set.grade ?? '',
      set.tm_full?.toFixed(1) ?? '',
      set.gc_percent ?? '',
      set.amplicon_size ?? '',
    ];
    return [
      'Rank\tForward Primer\tRT Primer\tReverse Primer\tScore\tGrade\tTm (°C)\tGC%\tAmplicon (bp)',
      cols.join('\t'),
    ].join('\n');
  }

  function fastaBlock() {
    const quality = tiered
      ? `Grade=${set.grade} S=${set.ranking.specificity.total}/${set.ranking.specificity.max}`
      : `Score=${set.total_score?.toFixed(1)}`;
    return [
      `>Primer_Set_${set.rank}_Forward  Tm=${set.tm_full?.toFixed(1)}C GC=${set.gc_percent}% ${quality}`,
      set.sequence,
      '>Primer_Set_RT_StemLoop',
      stemloop?.sequence ?? '',
      '>Primer_Set_Universal_Reverse',
      reverse?.sequence ?? '',
    ].join('\n');
  }

  const btns = [
    { label: 'Copy as TSV',   key: 'tsv',     action: () => copy(tsvRow(),      'tsv')     },
    { label: 'Copy as FASTA', key: 'fasta',   action: () => copy(fastaBlock(),  'fasta')   },
  ];

  return (
    <div className="flex flex-wrap gap-2 pt-1">
      {btns.map(({ label, key, action }) => (
        <button
          key={key}
          type="button"
          onClick={action}
          className={`text-xs px-3 py-1.5 rounded-lg border transition-all ${copied === key
              ? 'bg-teal-600 border-teal-600 text-white'
            : 'bg-white border-slate-300 text-slate-800 hover:border-teal-500 hover:text-teal-700'}`}
        >
          {copied === key ? 'Copied' : label}
        </button>
      ))}
    </div>
  );
}
