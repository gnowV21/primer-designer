import { createContext, useContext, useEffect, useState } from 'react';

export const THEMES = {
  pink: { label: 'Pink',  swatch: '#d67bda' },
  teal: { label: 'Teal',  swatch: '#0F6E56' },
  navy: { label: 'Navy',  swatch: '#273E74' },
};

const ThemeContext = createContext(null);

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(
    () => localStorage.getItem('hglab-theme') || 'pink'
  );

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('hglab-theme', theme);
  }, [theme]);

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export const useTheme = () => useContext(ThemeContext);
