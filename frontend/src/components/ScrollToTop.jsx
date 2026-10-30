/**
 * ScrollToTop — puts every route change back at the top of the page.
 *
 * The app scrolls the <main> element, not the document (App uses h-screen +
 * overflow-y-auto), so a router navigation leaves main.scrollTop exactly where
 * the previous page was. Scrolling down the designer to reach "Design Primers"
 * and then landing on /results already scrolled into the scoring section was the
 * visible symptom.
 *
 * `key` (not just `pathname`) is the dependency so that navigating to the SAME
 * route again — designing a second time, which re-enters /results — also resets.
 *
 * useLayoutEffect runs after the new route is committed but before paint, so the
 * page never flashes at the old offset.
 */
import { useLayoutEffect } from 'react';
import { useLocation } from 'react-router-dom';

export default function ScrollToTop({ containerRef }) {
  const { pathname, key } = useLocation();

  useLayoutEffect(() => {
    const el = containerRef?.current;
    if (el) el.scrollTop = 0;
    // Fallback: covers any view that scrolls the document instead of <main>.
    window.scrollTo(0, 0);
  }, [pathname, key, containerRef]);

  return null;
}
