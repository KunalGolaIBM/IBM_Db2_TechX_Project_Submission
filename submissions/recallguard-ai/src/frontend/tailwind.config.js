/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["'JetBrains Mono'", "ui-monospace", "monospace"],
      },
      colors: {
        ink: { 950: "#060b16", 900: "#0a1222", 850: "#0d172b", 800: "#111d35", 700: "#1a2848", 600: "#24365c" },
        line: "rgba(148,163,184,0.12)",
      },
      boxShadow: { glow: "0 0 0 1px rgba(56,189,248,.15), 0 10px 40px -10px rgba(14,165,233,.25)" },
      keyframes: { pulseRing: { "0%": { boxShadow: "0 0 0 0 rgba(248,113,113,.5)" }, "100%": { boxShadow: "0 0 0 10px rgba(248,113,113,0)" } } },
      animation: { pulseRing: "pulseRing 1.6s ease-out infinite" },
    },
  },
  plugins: [],
};
