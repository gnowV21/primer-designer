/**
 * NotFoundPage — any address that matches no route.
 *
 * Without it a mistyped URL rendered an empty page with no way forward.
 */
import { useEffect } from 'react';
import { Link } from 'react-router-dom';

export default function NotFoundPage() {
  useEffect(() => { document.title = 'HG Lab | Page not found'; }, []);

  return (
    <div className="max-w-lg mx-auto mt-20 text-center space-y-4">
      <h1 className="text-xl font-semibold text-slate-700">Page not found</h1>
      <p className="text-sm text-slate-500">This address does not match any page of the designer.</p>
      <Link
        to="/design"
        className="inline-block mt-2 px-5 py-2.5 rounded-xl bg-teal-600 text-white text-sm font-semibold hover:bg-teal-700 transition"
      >
        Go to Designer →
      </Link>
    </div>
  );
}
