/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['var(--font-sans)'],
        mono: ['var(--font-mono)'],
      },
      colors: {
        // Brand — controlled by CSS variables in index.css (switches with data-theme)
        'teal-50':  'var(--brand-50)',
        'teal-100': 'var(--brand-100)',
        'teal-200': 'var(--brand-200)',
        'teal-300': 'var(--brand-300)',
        'teal-400': 'var(--brand-400)',
        'teal-500': 'var(--brand-500)',
        'teal-600': 'var(--brand-600)',
        'teal-700': 'var(--brand-700)',
        'teal-800': 'var(--brand-800)',
        // Amber — warnings only
        'amber-50':  '#FFFBEB',
        'amber-100': '#FEF3C7',
        'amber-200': '#FDE68A',
        'amber-400': '#FBBF24',
        'amber-600': '#D97706',
        'amber-700': '#B45309',
        // Purple — Detection Method + Experimental Context groups
        'purple-50':  '#F5F3FF',
        'purple-100': '#EDE9FE',
        'purple-200': '#DDD6FE',
        'purple-300': '#C4B5FD',
        'purple-600': '#7C3AED',
        'purple-700': '#6D28D9',
        // Red — error states
        'red-50':   '#FEF2F2',
        'red-400':  '#F87171',
        'red-600':  '#DC2626',
      },
      borderRadius: {
        DEFAULT: '6px',
        sm:  '4px',
        md:  '8px',
        lg:  '12px',
        xl:  '16px',
        '2xl': '20px',
      },
      borderWidth: {
        DEFAULT: '1.5px',
      },
    },
  },
  plugins: [],
}
