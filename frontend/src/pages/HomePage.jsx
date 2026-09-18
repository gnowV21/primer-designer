import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { StemLoopIcon, ForwardPrimerIcon, PadlockIcon } from '../components/icons/PrimerIcons.jsx';

const primers = [
  {
    Icon: StemLoopIcon,
    iconClass: 'w-8 h-8 text-teal-600',
    name: 'Stem-loop RT Primer',
    role: 'Reverse transcription',
    desc: 'Hairpin ~44 nt + 3′ overhang of 6 nt complementary to the 3′ end of the mature miRNA. Extends cDNA from ~22 nt to >60 nt, enabling downstream qPCR amplification.',
    badge: '~50 nt',
    badgeColor: 'bg-teal-50 text-teal-700 border border-teal-100',
    roleColor: 'text-teal-600',
    accent: 'border-l-teal-400',
  },
  {
    Icon: ForwardPrimerIcon,
    iconClass: 'w-8 h-8 text-teal-500',
    name: 'Forward qPCR Primer',
    role: 'Specific amplification',
    desc: 'miRNA-specific region of 10–12 nt anchored at the 5′ end + a synthetic tail to raise Tm to 60°C. Anneals to the 5′ portion of the cDNA.',
    badge: '22–24 nt',
    badgeColor: 'bg-teal-50 text-teal-700 border border-teal-100',
    roleColor: 'text-teal-600',
    accent: 'border-l-teal-400',
  },
  {
    Icon: PadlockIcon,
    iconClass: 'w-7 h-7 text-slate-400',
    name: 'Universal Reverse Primer',
    role: 'Shared across all assays',
    desc: "Fixed sequence 5′-CCAGTGCAGGGTCCGAGGTA-3′. Disrupts the stem-loop hairpin and primes from the constant region — identical for every miRNA target.",
    badge: '20 nt · fixed',
    badgeColor: 'bg-slate-100 text-slate-600 border border-slate-200',
    roleColor: 'text-slate-500',
    accent: 'border-l-slate-300',
  },
];

const steps = [
  {
    step: '01',
    title: 'Enter miRNA',
    desc: 'Enter a miRBase ID (e.g. hsa-miR-21-5p) to auto-fill, or paste the mature sequence directly.',
    color: 'text-teal-600',
  },
  {
    step: '02',
    title: 'Adjust parameters',
    desc: 'Set Tm, salt concentration, GC content, primer length, and detection method (TaqMan / SYBR Green).',
    color: 'text-teal-500',
  },
  {
    step: '03',
    title: 'Get results',
    desc: 'Three optimized primers with thermodynamic parameters — ready for synthesis or export to CSV/PDF.',
    color: 'text-teal-400',
  },
];

const stats = [
  { value: '18–25 nt', label: 'Accepted miRNA length' },
  { value: '3',        label: 'Primers per design' },
  { value: 'Tm',       label: 'Thermodynamic validation' },
  { value: 'miRBase', label: 'Auto-fill from database' },
];

function IconCrosshair() {
  return (
    <svg viewBox="0 0 20 20" fill="none" className="w-4 h-4 text-teal-600 shrink-0" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
      <circle cx="10" cy="10" r="6.5" />
      <circle cx="10" cy="10" r="2.5" fill="currentColor" stroke="none" />
      <line x1="10" y1="1" x2="10" y2="4.5" />
      <line x1="10" y1="15.5" x2="10" y2="19" />
      <line x1="1" y1="10" x2="4.5" y2="10" />
      <line x1="15.5" y1="10" x2="19" y2="10" />
    </svg>
  );
}

function IconFilter() {
  return (
    <svg viewBox="0 0 20 20" fill="none" className="w-4 h-4 text-teal-600 shrink-0" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 4h16l-6 7v5l-4-2V11L2 4z" />
    </svg>
  );
}

function IconExtend() {
  return (
    <svg viewBox="0 0 20 20" fill="none" className="w-4 h-4 text-teal-600 shrink-0" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <line x1="2" y1="10" x2="18" y2="10" />
      <polyline points="13,5 18,10 13,15" />
      <line x1="2" y1="5" x2="2" y2="15" />
    </svg>
  );
}

function IconThermo() {
  return (
    <svg viewBox="0 0 20 20" fill="none" className="w-4 h-4 text-teal-600 shrink-0" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
      <path d="M10 12V4a2 2 0 0 0-4 0v8a4 4 0 1 0 4 0z" />
      <circle cx="8" cy="15" r="2.2" fill="currentColor" stroke="none" />
      <line x1="13" y1="5" x2="15.5" y2="5" />
      <line x1="13" y1="8" x2="15.5" y2="8" />
      <line x1="13" y1="11" x2="15.5" y2="11" />
    </svg>
  );
}

const advantages = [
  {
    Icon: IconCrosshair,
    title: 'High specificity',
    desc: 'The stem-loop structure physically excludes pre-miRNA and genomic DNA from RT — far fewer false positives than linear RT approaches.',
  },
  {
    Icon: IconFilter,
    title: 'Mature miRNA only',
    desc: 'The 6 nt 3′ overhang anchors to the very 3′ end of the mature sequence, discriminating it from the star strand and precursor.',
  },
  {
    Icon: IconExtend,
    title: 'Solves the short-RNA problem',
    desc: 'At only 22 nt, mature miRNAs are too short for conventional SYBR-based RT-PCR. The stem-loop extends the cDNA to >60 nt for efficient amplification.',
  },
  {
    Icon: IconThermo,
    title: 'Unified Tm across primers',
    desc: 'The synthetic tail on the forward primer and the fixed reverse primer are designed to match Tm — enabling clean single-temperature qPCR cycling.',
  },
];


export default function HomePage() {
  const navigate = useNavigate();
  useEffect(() => { document.title = 'HG Lab | Home'; }, []);

  return (
    <div className="max-w-3xl mx-auto space-y-10">

      {/* Hero */}
      <div className="rounded-2xl border border-teal-100 bg-gradient-to-br from-white via-teal-50 to-teal-100 px-8 py-12 text-center space-y-5 shadow-sm">
        <h1 className="text-2xl font-bold text-slate-800 leading-snug">
          Automated primer design for<br />
          <span className="text-teal-600">Stem-loop RT-qPCR</span>
        </h1>
        <p className="text-sm text-slate-500 max-w-xl mx-auto leading-relaxed">
          A tool for molecular biology researchers to design 3 specialized primers
          for mature miRNA quantification — fast, accurate, with thermodynamic validation.
        </p>
        <div className="flex items-center justify-center gap-3 pt-1">
          <button
            onClick={() => navigate('/design')}
            className="px-7 py-2.5 bg-gradient-to-r from-teal-600 to-teal-800 text-white text-sm font-medium rounded-xl shadow-sm hover:opacity-90 transition-all active:scale-[0.98]"
          >
            Start designing →
          </button>
          <a
            href="https://hglab.hcmus.edu.vn"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 px-4 py-2 border border-slate-200 text-slate-600 text-sm font-medium rounded-xl hover:bg-white transition-all"
          >
            <img src="/logo.png" alt="HG Lab" className="w-5 h-5 rounded-full object-cover shrink-0" />
            HG Lab
            <svg viewBox="0 0 12 12" fill="none" className="w-3 h-3 shrink-0" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M2 10L10 2M5 2h5v5" />
            </svg>
          </a>
        </div>
      </div>

      {/* Two entry points */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <button
          onClick={() => navigate('/design')}
          className="group text-left rounded-xl border border-teal-200 bg-white px-5 py-4 flex items-start gap-3 shadow-sm hover:shadow-md hover:border-teal-300 transition-all"
        >
          <span className="mt-0.5 shrink-0"><ForwardPrimerIcon className="w-7 h-7 text-teal-600" /></span>
          <div className="flex-1 space-y-0.5">
            <div className="flex items-center gap-1.5">
              <span className="text-sm font-semibold text-slate-800">Design new primers</span>
              <span className="text-teal-600 transition-transform group-hover:translate-x-0.5">→</span>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Start from a miRBase ID or mature sequence and generate the three optimized primers.
            </p>
          </div>
        </button>

        <button
          onClick={() => navigate('/analyze')}
          className="group text-left rounded-xl border border-slate-200 bg-white px-5 py-4 flex items-start gap-3 shadow-sm hover:shadow-md hover:border-teal-300 transition-all"
        >
          <span className="mt-1 shrink-0 inline-flex w-7 h-7 items-center justify-center scale-[1.6] origin-center"><IconThermo /></span>
          <div className="flex-1 space-y-0.5">
            <div className="flex items-center gap-1.5">
              <span className="text-sm font-semibold text-slate-800">Analyze existing primers</span>
              <span className="text-teal-600 transition-transform group-hover:translate-x-0.5">→</span>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Already have a primer set? Paste the three primers + miRNA to compute Tm, dimers, and specificity.
            </p>
          </div>
        </button>
      </div>

      {/* Stats bar */}
      <div className="grid grid-cols-4 gap-3">
        {stats.map(({ value, label }) => (
          <div
            key={label}
            className="rounded-xl border border-slate-200 bg-white px-4 py-4 text-center space-y-1 shadow-sm"
          >
            <p className="text-lg font-black text-teal-600 leading-none tabular-nums">{value}</p>
            <p className="text-xs text-slate-400 leading-snug">{label}</p>
          </div>
        ))}
      </div>

      {/* 3 Primers */}
      <div>
        <h2 className="text-sm font-semibold text-slate-600 mb-4">Three primers designed per run</h2>
        <div className="grid grid-cols-1 gap-3">
          {primers.map(({ Icon, iconClass, name, role, desc, badge, badgeColor, roleColor, accent }) => (
            <div
              key={name}
              className={`flex items-start gap-4 rounded-xl border border-slate-200 bg-white px-5 py-4 border-l-4 ${accent} shadow-sm hover:shadow-md transition-shadow`}
            >
              <span className="mt-0.5 shrink-0">
                <Icon className={iconClass} />
              </span>
              <div className="flex-1 space-y-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-semibold text-slate-800">{name}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${badgeColor}`}>
                    {badge}
                  </span>
                </div>
                <p className={`text-xs font-medium ${roleColor}`}>{role}</p>
                <p className="text-xs text-slate-400 leading-relaxed">{desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Why stem-loop RT-qPCR */}
      <div>
        <h2 className="text-sm font-semibold text-slate-600 mb-1">Why stem-loop RT-qPCR?</h2>
        <p className="text-xs text-slate-400 mb-4 leading-relaxed">
          Mature miRNAs are only ~22 nt — too short for conventional RT-PCR. Chen et al. (2005) solved this with a
          hairpin RT primer that physically discriminates mature from pre-miRNA and extends the cDNA to enable qPCR.
        </p>
        <div className="grid grid-cols-2 gap-3">
          {advantages.map(({ Icon, title, desc }) => (
            <div
              key={title}
              className="rounded-xl border border-slate-200 bg-white px-4 py-4 space-y-1.5 shadow-sm hover:shadow-md transition-shadow"
            >
              <div className="flex items-center gap-2">
                <Icon />
                <span className="text-sm font-semibold text-slate-700">{title}</span>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* How it works */}
      <div>
        <h2 className="text-sm font-semibold text-slate-600 mb-4">How to use</h2>
        <div className="grid grid-cols-3 gap-4">
          {steps.map((s) => (
            <div
              key={s.step}
              className="rounded-xl border border-slate-200 bg-white px-4 py-5 space-y-2 shadow-sm hover:shadow-md transition-shadow"
            >
              <span className={`text-3xl font-black ${s.color} leading-none`}>{s.step}</span>
              <p className="text-sm font-semibold text-slate-700">{s.title}</p>
              <p className="text-xs text-slate-400 leading-relaxed">{s.desc}</p>
            </div>
          ))}
        </div>
      </div>


    </div>
  );
}
