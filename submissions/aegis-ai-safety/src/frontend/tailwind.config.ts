import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "hsl(var(--canvas))",
        surface: "hsl(var(--surface))",
        "surface-2": "hsl(var(--surface-2))",
        line: "hsl(var(--line))",
        ink: "hsl(var(--ink))",
        muted: "hsl(var(--muted))",
        accent: {
          DEFAULT: "hsl(var(--accent))",
          soft: "hsl(var(--accent-soft))",
        },
        supported: {
          DEFAULT: "hsl(var(--supported))",
          soft: "hsl(var(--supported-soft))",
        },
        contradicted: {
          DEFAULT: "hsl(var(--contradicted))",
          soft: "hsl(var(--contradicted-soft))",
        },
        insufficient: {
          DEFAULT: "hsl(var(--insufficient))",
          soft: "hsl(var(--insufficient-soft))",
        },
        verror: {
          DEFAULT: "hsl(var(--verror))",
          soft: "hsl(var(--verror-soft))",
        },
        // Backwards-compatible aliases used by the retained evidence components.
        bg: "hsl(var(--canvas))",
        panel: "hsl(var(--surface))",
        "panel-2": "hsl(var(--surface-2))",
        border: "hsl(var(--line))",
        fg: "hsl(var(--ink))",
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      boxShadow: {
        panel:
          "0 1px 2px rgba(24,24,22,0.03), 0 18px 50px -30px rgba(24,24,22,0.18)",
      },
      keyframes: {
        "fade-up": {
          from: { opacity: "0", transform: "translateY(10px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        pulsebar: {
          "0%, 100%": { opacity: "0.35", transform: "scaleX(0.7)" },
          "50%": { opacity: "1", transform: "scaleX(1)" },
        },
      },
      animation: {
        "fade-up": "fade-up 500ms cubic-bezier(0.22,1,0.36,1) both",
        pulsebar: "pulsebar 1.5s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
