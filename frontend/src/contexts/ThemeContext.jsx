import { createContext, useContext, useEffect } from 'react';

// One theme: HG Lab navy (#273E74). The palette lives in CSS variables (index.css,
// --brand-*), so a future theme is one variable block; there is no theme switcher
// (UI review 2026-11-23: the pink and teal themes failed WCAG contrast).
export const THEME = 'navy';

const ThemeContext = createContext({ theme: THEME });

export function ThemeProvider({ children }) {
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', THEME);
    try { localStorage.removeItem('hglab-theme'); } catch { /* storage blocked */ }
  }, []);

  return <ThemeContext.Provider value={{ theme: THEME }}>{children}</ThemeContext.Provider>;
}

export const useTheme = () => useContext(ThemeContext);
