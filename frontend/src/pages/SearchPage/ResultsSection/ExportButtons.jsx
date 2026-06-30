// ExportButtons — copy primers to clipboard in various formats.

import { useState } from 'react';

export default function ExportButtons({ set, stemloop, reverse }) {
  const [copied, setCopied] = useState('');

  function copy(text, label) {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(label);
      setTimeout(() => setCopied(''), 2000);
    });
  }

  function tsvRow() {
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
    return [
      `>Primer_Set_${set.rank}_Forward  Tm=${set.tm_full?.toFixed(1)}C GC=${set.gc_percent}% Score=${set.total_score?.toFixed(1)}`,
      set.sequence,
      '>Primer_Set_RT_StemLoop',
      stemloop?.sequence ?? '',
      '>Primer_Set_Universal_Reverse',
      reverse?.sequence ?? '',
    ].join('\n');
  }

  const btns = [
    { label: 'Copy forward',  key: 'forward', action: () => copy(set.sequence,  'forward') },
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
          className={`text-xs px-3 py-1.5 rounded-lg border transition-all
            ${copied === key
              ? 'bg-teal-600 border-teal-600 text-white'
              : 'bg-white border-gray-200 text-gray-600 hover:border-teal-400 hover:text-teal-700'
            }`}
        >
          {copied === key ? '✓ Copied' : label}
        </button>
      ))}
    </div>
  );
}
