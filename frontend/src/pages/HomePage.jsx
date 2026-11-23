import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { StemLoopIcon, ForwardPrimerIcon, PadlockIcon } from '../components/icons/PrimerIcons.jsx';

// Lengths stated as the engine produces them (backend constants.FORWARD_SPECIFIC_LENGTHS,
// forward primers of the 4.0.0 freeze: 18–27 nt, 82% of the #1 primers 20–24 nt).
const primers = [
  {
    Icon: StemLoopIcon,
    iconClass: 'w-8 h-8 text-teal-600',
    name: 'Stem-loop RT primer',
    role: 'Reverse transcription',
    desc: 'A 44-nt hairpin body plus a 6-nt 3′ overhang that pairs with the 3′ end of the mature miRNA. It extends the cDNA from about 22 nt to more than 60 nt so that qPCR can amplify it.',
    badge: '50 nt',
    accent: 'border-l-teal-500',
  },
  {
    Icon: ForwardPrimerIcon,
    iconClass: 'w-8 h-8 text-teal-600',
    name: 'Forward qPCR primer',
    role: 'Specific amplification',
    desc: 'A miRNA-specific region of 12–17 nt from the 5′ end of the miRNA, plus a synthetic 5′ tail that brings the Tm to about 60 °C.',
    badge: '18–27 nt',
    accent: 'border-l-teal-500',
  },
  {
    Icon: PadlockIcon,
    iconClass: 'w-7 h-7 text-slate-600',
    name: 'Universal reverse primer',
    role: 'The same for every assay',
    desc: 'A fixed sequence that primes from the stem-loop body, identical for every miRNA target.',
    seq: 'CCAGTGCAGGGTCCGAGGTA',
    badge: '20 nt, fixed',
    accent: 'border-l-slate-400',
  },
];

const steps = [
  {
    step: '1',
    title: 'Enter the miRNA',
    desc: <>Type a miRBase name such as <span className="whitespace-nowrap">hsa-miR-21-5p</span> or an accession, or paste the mature sequence.</>,
  },
  {
    step: '2',
    title: 'Change parameters if needed',
    desc: 'Every parameter starts at a validated default. Open Parameters to change the Tm window, the reaction conditions, the overhang length or SYBR Green / TaqMan.',
  },
  {
    step: '3',
    title: 'Get the primers',
    desc: 'Three ranked primer sets with their checks, ready to export as PDF, CSV or FASTA. You can change parameters and re-run on the results page.',
  },
];

export default function HomePage() {
  const navigate = useNavigate();
  useEffect(() => { document.title = 'HG Lab | Home'; }, []);

  return (
    <div className="max-w-3xl mx-auto space-y-10">

      {/* Hero: one sentence, one action */}
      <div className="rounded-2xl border border-teal-100 bg-teal-50 px-5 sm:px-8 py-8 sm:py-12 text-center space-y-5">
        <h1 className="text-2xl font-bold text-slate-800 leading-snug">
          Primer design for stem-loop RT-qPCR
        </h1>
        <p className="text-sm text-slate-700 max-w-xl mx-auto leading-relaxed">
          Designs the three primers needed to quantify a mature miRNA by stem-loop RT-qPCR, with
          thermodynamic and specificity checks.
        </p>
          <button
          type="button"
            onClick={() => navigate('/design')}
          className="whitespace-nowrap px-7 py-2.5 bg-teal-600 text-white text-sm font-semibold rounded-xl shadow-sm hover:bg-teal-700 transition-all active:scale-[0.98]"
          >
          Start designing
        </button>
      </div>

      {/* The three primers */}
      <section>
        <h2 className="text-base font-semibold text-slate-800 mb-4">Three primers per design</h2>
        <div className="grid grid-cols-1 gap-3">
          {primers.map(({ Icon, iconClass, name, role, desc, seq, badge, accent }) => (
            <div
              key={name}
              className={`flex items-start gap-4 rounded-xl border border-slate-200 bg-white px-5 py-4 border-l-4 ${accent}`}
            >
              <span className="mt-0.5 shrink-0">
                <Icon className={iconClass} />
              </span>
              <div className="flex-1 min-w-0 space-y-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-semibold text-slate-800">{name}</span>
                  <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-slate-100 text-slate-700 border border-slate-200">
                    {badge}
                  </span>
                </div>
                <p className="text-xs font-medium text-teal-700">{role}</p>
                <p className="text-xs text-slate-700 leading-relaxed">{desc}</p>
                {seq && <code className="seq-block text-xs text-slate-800">5′-{seq}-3′</code>}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Why stem-loop RT-qPCR: one paragraph, cautious and cited */}
      <section>
        <h2 className="text-base font-semibold text-slate-800 mb-2">Why stem-loop RT-qPCR?</h2>
        <p className="text-sm text-slate-700 leading-relaxed">
          A mature miRNA is only about 22 nt, too short for conventional RT-PCR. The stem-loop RT
          primer of Chen et al. (2005) pairs with the miRNA&apos;s 3′ end and lengthens the cDNA so that a
          forward primer and a universal reverse primer can amplify it at one annealing temperature.
          The stem-loop favors the mature miRNA over its precursor, but this discrimination is not
          guaranteed for every miRNA; include a pre-miRNA control when it matters.
        </p>
      </section>

      {/* How to use */}
      <section>
        <h2 className="text-base font-semibold text-slate-800 mb-4">How to use</h2>
        <ol className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {steps.map((s) => (
            <li key={s.step} className="rounded-xl border border-slate-200 bg-white px-4 py-5 space-y-2">
              <span className="inline-flex w-7 h-7 items-center justify-center rounded-full bg-teal-600 text-white text-sm font-bold">
                {s.step}
              </span>
              <p className="text-sm font-semibold text-slate-800">{s.title}</p>
              <p className="text-xs text-slate-700 leading-relaxed">{s.desc}</p>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
