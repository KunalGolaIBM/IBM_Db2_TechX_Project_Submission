/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      colors: {
        primary: '#A855F7',
        glass: 'rgba(255,255,255,0.05)',
        dark: {
          bg: '#0f0c29',
          panel: 'rgba(15,12,41,0.7)',
        },
      },
      backgroundImage: {
        'dark-gradient': 'linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%)',
      },
    },
  },
  plugins: [],
};
