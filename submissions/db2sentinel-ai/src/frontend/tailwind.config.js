/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        sentinel: {
          bg: '#0A1128',
          card: '#132238',
          cardHover: '#182C48',
          border: '#1E3A5F',
          ibmBlue: '#0F62FE',
          cyan: '#00D2FF',
          purple: '#8A3FFC',
          red: '#FA4D56',
          amber: '#F1C21B',
          green: '#42BE65'
        }
      }
    },
  },
  plugins: [],
}
