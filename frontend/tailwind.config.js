/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Brand teal — lab primary (CLAUDE.md spec)
        'teal-50':  '#E1F5EE',
        'teal-100': '#C5EEE0',
        'teal-200': '#5DCAA5',
        'teal-500': '#1A9E74',
        'teal-600': '#0F6E56',
        'teal-700': '#0A5A40',
        'teal-800': '#085041',
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
