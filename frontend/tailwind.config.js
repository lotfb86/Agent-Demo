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
          ink: '#1f2a36',
          steel: '#5d6b79',
          slate: '#c8d0d8',
          signal: '#ff6f3c',
          mint: '#2bb673',
          amber: '#f2a65a',
          danger: '#d64545',
          canvas: '#f6f8fb',
          panel: '#ffffff',
        },
      },
      boxShadow: {
        glow: '0 18px 45px -24px rgba(13, 24, 37, 0.35)',
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
      },
      animation: {
        rise: 'rise 360ms ease-out both',
        pulse3: 'pulse3 1.4s ease-in-out infinite',
        'fade-in': 'fadeIn 300ms ease-out both',
        'slide-in': 'slideIn 280ms ease-out both',
        'glow-pulse': 'glowPulse 2s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
