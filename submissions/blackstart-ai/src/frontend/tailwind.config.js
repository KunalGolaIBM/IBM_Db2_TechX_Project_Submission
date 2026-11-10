/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: {
          950: '#03050A',
          900: '#05070E',
          850: '#070B14',
          800: '#0A0F1B',
          700: '#0E1524',
          600: '#141C2E',
          500: '#1B2537',
          400: '#273349',
        },
        accent: {
          DEFAULT: '#22D3EE',
          bright: '#67E8F9',
          dim: '#0E7490',
        },
        signal: {
          emerald: '#34D399',
          amber: '#FBBF24',
          red: '#F87171',
        },
      },
      fontFamily: {
        display: ['"Space Grotesk"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      boxShadow: {
        panel: '0 1px 0 0 rgba(255,255,255,0.03) inset, 0 18px 50px -24px rgba(0,0,0,0.85)',
        'panel-hover': '0 0 0 1px rgba(34,211,238,0.18), 0 22px 55px -24px rgba(0,0,0,0.9)',
        glow: '0 0 28px -8px rgba(34,211,238,0.45)',
        'glow-red': '0 0 28px -8px rgba(248,113,113,0.45)',
        'glow-amber': '0 0 28px -8px rgba(251,191,36,0.4)',
        'glow-emerald': '0 0 28px -8px rgba(52,211,153,0.4)',
      },
      keyframes: {
        'fade-up': {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'pulse-dot': {
          '0%, 100%': { opacity: '1', transform: 'scale(1)' },
          '50%': { opacity: '0.45', transform: 'scale(0.85)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-420px 0' },
          '100%': { backgroundPosition: '420px 0' },
        },
        'flow-line': {
          '0%': { strokeDashoffset: '24' },
          '100%': { strokeDashoffset: '0' },
        },
        sweep: {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(100%)' },
        },
      },
      animation: {
        'fade-up': 'fade-up 0.35s cubic-bezier(0.22,1,0.36,1) both',
        'pulse-dot': 'pulse-dot 2s ease-in-out infinite',
        shimmer: 'shimmer 1.6s linear infinite',
        'flow-line': 'flow-line 1.1s linear infinite',
        sweep: 'sweep 2.2s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};
