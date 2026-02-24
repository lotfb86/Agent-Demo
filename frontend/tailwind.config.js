/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
      },
      colors: {
        rpmx: {
          // Text hierarchy — exact spec
          ink:    '#0F172A',   // Primary text — very dark slate
          steel:  '#475569',   // Secondary text — medium gray
          muted:  '#94A3B8',   // Tertiary / disabled
          // Surfaces
          canvas: '#F8FAFC',   // App background
          panel:  '#FFFFFF',   // Cards / modals
          deep:   '#F1F5F9',   // Subtle hover / elevated bg
          wash:   '#E2E8F0',   // Borders / dividers
          // Brand
          signal: '#3B82F6',   // Primary blue
          // Status
          mint:   '#059669',   // Success green
          amber:  '#D97706',   // Warning amber
          danger: '#DC2626',   // Error red
          // Legacy aliases (keep for backward compat)
          slate:  '#E2E8F0',
        },
      },
      fontSize: {
        'display': ['48px', { lineHeight: '1.1', fontWeight: '700', letterSpacing: '-0.02em' }],
        'h1':      ['32px', { lineHeight: '1.2', fontWeight: '700', letterSpacing: '-0.01em' }],
        'h2':      ['24px', { lineHeight: '1.3', fontWeight: '600' }],
        'h3':      ['18px', { lineHeight: '1.4', fontWeight: '600' }],
        'h4':      ['14px', { lineHeight: '1.4', fontWeight: '600' }],
        'body':    ['14px', { lineHeight: '1.6' }],
        'caption': ['12px', { lineHeight: '1.5' }],
        'micro':   ['11px', { lineHeight: '1.4' }],
        'tiny':    ['10px', { lineHeight: '1.4', letterSpacing: '0.05em' }],
      },
      boxShadow: {
        'card':   '0 1px 3px 0 rgba(0,0,0,0.06), 0 1px 2px -1px rgba(0,0,0,0.04)',
        'hover':  '0 4px 12px 0 rgba(0,0,0,0.10), 0 2px 4px -1px rgba(0,0,0,0.06)',
        'focus':  '0 0 0 3px rgba(59,130,246,0.18)',
        'modal':  '0 20px 40px 0 rgba(0,0,0,0.14)',
        'inset':  'inset 0 1px 2px 0 rgba(0,0,0,0.04)',
        // keep legacy
        'soft':        '0 1px 3px rgba(0,0,0,0.05)',
        'elevated':    '0 2px 8px rgba(0,0,0,0.10)',
        'card-hover':  '0 4px 12px rgba(0,0,0,0.10)',
        'inner-soft':  'inset 0 1px 2px rgba(0,0,0,0.05)',
      },
      borderRadius: {
        DEFAULT: '8px',
        'sm': '6px',
        'md': '8px',
        'lg': '12px',
        'xl': '16px',
        '2xl': '20px',
        'full': '9999px',
      },
      spacing: {
        '18': '72px',
        '22': '88px',
        '26': '104px',
      },
      keyframes: {
        fadeIn:  { '0%': { opacity: '0' }, '100%': { opacity: '1' } },
        slideIn: { '0%': { opacity: '0', transform: 'translateY(6px)' }, '100%': { opacity: '1', transform: 'translateY(0)' } },
        pulse3:  { '0%,80%,100%': { opacity: '0.3', transform: 'scale(0.8)' }, '40%': { opacity: '1', transform: 'scale(1)' } },
        shimmer: { '0%': { backgroundPosition: '-600px 0' }, '100%': { backgroundPosition: '600px 0' } },
      },
      animation: {
        'fade-in':  'fadeIn 250ms ease-out both',
        'slide-in': 'slideIn 250ms ease-out both',
        'pulse3':   'pulse3 1.4s ease-in-out infinite',
        'shimmer':  'shimmer 1.6s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
