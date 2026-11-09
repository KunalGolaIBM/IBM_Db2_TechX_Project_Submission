/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        forest: {
          50: '#f2f8f4',
          100: '#e1efe6',
          200: '#c2decb',
          300: '#95c4a5',
          400: '#64a37b',
          500: '#3e8457',
          600: '#2d6a44',
          700: '#235336',
          800: '#1c422c',
          900: '#0d2d20',
          950: '#061a12',
        },
        sage: {
          50: '#f6f8f6',
          100: '#ebf1ec',
          200: '#d7e3da',
          300: '#b7ccbd',
          400: '#92ae9b',
          500: '#6f8f79',
          600: '#53725d',
          700: '#425b4b',
          800: '#364a3d',
          900: '#1b261f',
        },
        carbon: {
          50: '#edfcf4',
          100: '#d3f8e4',
          200: '#aaefce',
          300: '#72e1b1',
          400: '#38cb8d',
          500: '#14b178',
          600: '#0a9063',
          700: '#0a7351',
          800: '#0c5c43',
          900: '#0c4c38',
          950: '#052b20',
        },
        ink: {
          900: '#0b1c15',
          800: '#142a20',
          700: '#223c30',
          600: '#385345',
          500: '#557062',
          400: '#7e9689',
          300: '#acc0b4',
          200: '#d8e4dd',
          100: '#edf4f0',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
      boxShadow: {
        card: '0 1px 3px rgba(0, 0, 0, 0.04), 0 4px 12px rgba(11, 40, 28, 0.03)',
        'card-hover': '0 4px 6px rgba(0, 0, 0, 0.04), 0 12px 24px rgba(11, 40, 28, 0.07)',
        glow: '0 0 24px rgba(16, 185, 129, 0.25)',
      },
      borderRadius: {
        '2xl': '16px',
        '3xl': '24px',
      }
    },
  },
  plugins: [],
}
