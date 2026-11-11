/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        gaming: ['Orbitron', 'sans-serif'],
        'mono-code': ['JetBrains Mono', 'monospace'],
      },
    },
  },
  plugins: [],
}
