import { Link } from 'react-router-dom';

export default function Footer() {
  return (
    <footer className="h-9 flex items-center justify-between gap-3 px-4 sm:px-6 border-t border-slate-200 bg-white shrink-0">
      <span className="text-xs text-slate-500 truncate">
        HG Lab<span className="hidden sm:inline"> · Human Genetics Laboratory, HCMUS</span> ·{' '}
        <Link to="/benchmark" className="text-teal-600 hover:underline">
          Benchmark
        </Link>
      </span>
      <span className="text-xs text-slate-500 shrink-0">
        <span className="hidden sm:inline">Contact: </span>
        <a
          href="https://hglab.hcmus.edu.vn"
          target="_blank"
          rel="noopener noreferrer"
          className="text-teal-600 hover:underline"
        >
          hglab.hcmus.edu.vn
        </a>
      </span>
    </footer>
  );
}
