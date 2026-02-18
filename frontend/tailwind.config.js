/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Space Grotesk"', 'system-ui', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
      },
      colors: {
        rpmx: {
          ink: '#1a2332',
          steel: '#64748b',
          slate: '#cbd5e1',
          signal: '#ff6f3c',
          mint: '#10b981',
          amber: '#f59e0b',
          danger: '#ef4444',
          canvas: '#f8fafc',
          panel: '#ffffff',
          // Extended palette for depth
          deep: '#0f172a',
          muted: '#94a3b8',
          wash: '#f1f5f9',
        },
      },
      boxShadow: {
        'glow': '0 20px 50px -20px rgba(15, 23, 42, 0.18)',
        'card': '0 1px 3px 0 rgba(0, 0, 0, 0.04), 0 1px 2px -1px rgba(0, 0, 0, 0.04)',
        'card-hover': '0 10px 25px -8px rgba(15, 23, 42, 0.12), 0 4px 10px -4px rgba(15, 23, 42, 0.04)',
        'elevated': '0 4px 12px -2px rgba(15, 23, 42, 0.08), 0 2px 4px -2px rgba(15, 23, 42, 0.04)',
        'inner-soft': 'inset 0 1px 2px rgba(0, 0, 0, 0.04)',
      },
      borderRadius: {
        '2xl': '1rem',
        '3xl': '1.25rem',
      },
      keyframes: {
        rise: {
          '0%': { opacity: '0', transform: 'translateY(14px)' },
          '100%': { opacity: '1', transform: 'translateY(0px)' },
        },
        pulse3: {
          '0%, 80%, 100%': { opacity: '0.3', transform: 'scale(0.8)' },
          '40%': { opacity: '1', transform: 'scale(1)' },
        },
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideIn: {
          '0%': { opacity: '0', transform: 'translateX(-8px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        glowPulse: {
          '0%, 100%': { boxShadow: '0 0 12px -4px rgba(255,111,60,0.15)' },
          '50%': { boxShadow: '0 0 24px -4px rgba(255,111,60,0.35)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
      animation: {
        rise: 'rise 360ms ease-out both',
        pulse3: 'pulse3 1.4s ease-in-out infinite',
        'fade-in': 'fadeIn 300ms ease-out both',
        'slide-in': 'slideIn 280ms ease-out both',
        'glow-pulse': 'glowPulse 2s ease-in-out infinite',
        shimmer: 'shimmer 2s linear infinite',
      },
    },
  },
  plugins: [],
}
