/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['var(--font-sans)'],
        mono: ['var(--font-mono)'],
      },
      // Type scale — one notch above Tailwind's default (xs 12/sm 14) because
      // `text-xs` is this app's de-facto body size, not a caption size. Raising
      // it here lifts ~300 call sites at once instead of rewriting each one.
      // Line-heights target ~1.5 for readable running text; xs stays a little
      // tighter since it also carries dense metric rows.
      fontSize: {
        xs:   ['0.8125rem', { lineHeight: '1.45' }],  // 13px
        sm:   ['0.9375rem', { lineHeight: '1.5'  }],  // 15px
        base: ['1rem',      { lineHeight: '1.5'  }],  // 16px
        lg:   ['1.125rem',  { lineHeight: '1.45' }],  // 18px
        xl:   ['1.25rem',   { lineHeight: '1.4'  }],  // 20px
        '2xl':['1.5rem',    { lineHeight: '1.3'  }],  // 24px
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
        // Orange — the HIGH tier of the 4-level off-target risk scale
        // (SAFE teal -> MEDIUM amber -> HIGH orange -> CRITICAL red). It exists
        // only so that scale keeps four distinguishable steps; do not use it as
        // a general warning colour, that is amber's job.
        'orange-50':  '#FFF7ED',
        'orange-200': '#FED7AA',
        'orange-300': '#FDBA74',
        'orange-500': '#F97316',
        'orange-600': '#EA580C',
        'orange-700': '#C2410C',
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
