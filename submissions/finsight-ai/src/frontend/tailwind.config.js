/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // FinSight AI Exact Brand Palette (Stage 8)
        forest: {
          DEFAULT: '#15370D',
          50: '#f3f6f2',
          100: '#e3ece0',
          200: '#c7dac2',
          300: '#a3c29c',
          400: '#7ba573',
          500: '#58884f',
          600: '#416d39',
          700: '#32562c',
          800: '#233f1e',
          900: '#15370D', // Exact Brand Forest Green
          950: '#0c2207', // Deep forest night
        },
        sage: {
          DEFAULT: '#728E6D',
          50: '#f5f7f4',
          100: '#e8ede6',
          200: '#d2ddd0',
          300: '#b4c4af',
          400: '#94a98f',
          500: '#728E6D', // Exact Brand Sage Green
          600: '#5a7356',
          700: '#465b43',
          800: '#3a4b37',
          900: '#303e2e',
          950: '#182117',
        },
        gold: {
          DEFAULT: '#E5CD82',
          50: '#fdfbf6',
          100: '#faf4e4',
          200: '#f4e7c4',
          300: '#ebd79e',
          400: '#E5CD82', // Exact Brand Muted Gold
          500: '#d6b862',
          600: '#bb9948',
          700: '#947539',
          800: '#7a5f33',
          900: '#674f2d',
          950: '#3a2b16',
        },
        cream: {
          DEFAULT: '#FFF2B4',
          50: '#fffef9',
          100: '#fffbf0',
          200: '#FFF2B4', // Exact Brand Butter Cream
          300: '#fee78e',
          400: '#fcd361',
          500: '#f7b738',
        },
        // Refined fintech neutral surfaces: warm cream-tinted light, deep forest-tinted dark
        fintech: {
          lightBg: '#FAF8F3',    // Cream-tinted neutral surface
          lightCard: '#FFFFFF',
          lightBorder: '#E6E2D8',
          lightText: '#152912',  // Deep readable green-black
          lightMuted: '#5C6C58',
          
          darkBg: '#0b160a',     // Deep forest night surface
          darkCard: '#10210e',   // Deep forest card surface
          darkBorder: '#1c3619',
          darkText: '#F5F7F2',
          darkMuted: '#95A890',
        },
        brand: {
          50: '#f8fafc',
          100: '#f1f5f9',
          200: '#e2e8f0',
          300: '#cbd5e1',
          400: '#94a3b8',
          500: '#64748b',
          600: '#475569',
          700: '#334155',
          800: '#1e293b',
          900: '#0f172a',
          950: '#020617',
        },
        accent: {
          blue: '#0284c7', // refined IBM/Apple fintech deep sky blue
          indigo: '#4f46e5',
          emerald: '#059669',
          amber: '#d97706',
        }
      },
      fontFamily: {
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          '"Segoe UI"',
          'Roboto',
          '"Helvetica Neue"',
          'Arial',
          'sans-serif',
        ],
        mono: [
          'ui-monospace',
          'SFMono-Regular',
          'Menlo',
          'Monaco',
          'Consolas',
          'monospace',
        ],
      },
      letterSpacing: {
        tightest: '-0.035em',
        tighter: '-0.025em',
        tight: '-0.015em',
      },
    },
  },
  plugins: [],
}
