import { Link } from 'react-router-dom';
import useAlgorithmVersion from '../hooks/useAlgorithmVersion.js';

// Static footer at the end of each page (inside the scroll container), so it
// never takes a fixed strip of the viewport.
export default function Footer() {
  const version = useAlgorithmVersion();
  return (
    <footer className="mt-10 flex flex-wrap items-center justify-between gap-x-4 gap-y-1 px-4 sm:px-6 py-3 border-t border-slate-200 text-xs text-slate-600">
      <span>
        HG Lab, Human Genetics Laboratory, HCMUS
      </span>
      <span className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <Link to="/benchmark" className="text-teal-700 hover:underline">Validation</Link>
        {version && <span data-testid="algorithm-version">Algorithm v{version}</span>}
        <a href="https://hglab.hcmus.edu.vn" target="_blank" rel="noopener noreferrer"
          className="text-teal-700 hover:underline">
          hglab.hcmus.edu.vn
        </a>
      </span>
    </footer>
  );
}
