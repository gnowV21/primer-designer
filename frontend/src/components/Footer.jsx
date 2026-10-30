import { Link } from 'react-router-dom';

export default function Footer() {
  return (
    <footer className="h-9 flex items-center justify-between px-6 border-t border-slate-200 bg-white shrink-0">
      <span className="text-xs text-slate-500">
        HG Lab · Human Genetics Laboratory, HCMUS ·{' '}
        <Link to="/benchmark" className="text-teal-600 hover:underline">
          Benchmark
        </Link>
      </span>
      <span className="text-xs text-slate-500">
        Contact:{' '}
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
