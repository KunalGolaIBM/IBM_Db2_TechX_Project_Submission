/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ibm: {
          blue: '#0F62FE',
          'blue-hover': '#0353E9',
          dark: '#161616',
          navy: '#001D6C',
          gray: '#F4F4F4',
          'gray-hover': '#E8E8E8',
          border: '#E0E0E0',
          text: '#161616',
          muted: '#525252',
          success: '#198038',
          danger: '#DA1E28',
          warning: '#F1C21B',
          purple: '#8A3FFC'
        }
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'monospace']
      }
    },
  },
  plugins: [],
}
