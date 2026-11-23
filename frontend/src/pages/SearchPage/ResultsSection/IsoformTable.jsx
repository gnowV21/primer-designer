// Most common 3′ isoforms (isomiRdb, pooled) — inside the isomiR "Why" on /results.
// Every value and label comes from the API (stemloop_rt.three_prime_isomir); nothing
// about RT capture is computed here. When the reference is not assessed, one line.

// One decimal, so close shares stay distinct (miR-27b-3p: 38.0 % vs 38.1 %).
const share = (x) => (x == null ? '—' : `${(100 * x).toFixed(1)} %`);

function End({ rna, diffAt }) {
  if (!rna) return '—';
  if (diffAt == null) return rna;
  return (
    <>
      {rna.slice(0, diffAt)}
      <span className="font-bold text-amber-900 underline">{rna.slice(diffAt)}</span>
    </>
  );
}

export default function IsoformTable({ iso }) {
  const variants = iso?.dominant_3prime_variants || [];
  if (iso?.reference_note) {
    return <p data-testid="isomir-reference-note">{iso.reference_note}.</p>;
  }
  if (!variants.length || !variants[0].rt_capture) return null;
  return (
    <div data-testid="isomir-table">
      <p className="font-semibold">Most common 3′ isoforms (isomiRdb, pooled)</p>
      <table className="w-full table-fixed mt-1 text-left">
        <thead className="text-amber-700">
          <tr>
            <th className="font-medium w-[21%] pr-1">3′ end</th>
            <th className="font-medium w-[24%] pr-2">Type</th>
            <th className="font-medium w-[19%] pr-2">Share of reads</th>
            <th className="font-medium pr-1">Expected RT capture</th>
          </tr>
        </thead>
        <tbody className="align-top">
          <tr className="border-t border-amber-200">
            <td className="seq pr-1"><End rna={iso.canonical_end_rna} /></td>
            <td className="pr-2">miRBase 22.1 end</td>
            <td className="pr-2 tabular-nums">{share(iso.canonical_3prime_share_pooled)}</td>
            <td className="pr-1 break-words">primer target</td>
          </tr>
          {variants.map((v) => (
            <tr key={v.sequence_dna} className="border-t border-amber-200" data-testid="isomir-row">
              <td className="seq pr-1"><End rna={v.end_rna} diffAt={v.end_diff_at} /></td>
              <td className="pr-2">{v.type_label}</td>
              <td className="pr-2 tabular-nums">{share(v.pooled_share)}</td>
              <td className="pr-1 break-words" title={v.rt_capture.note || undefined}>{v.rt_capture.label}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
