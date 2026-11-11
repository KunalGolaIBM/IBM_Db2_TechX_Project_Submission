import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: `npm run dev` serves the UI on 5173 and proxies /api to the FastAPI
// backend on 127.0.0.1:8000 (CORS_ORIGINS default in .env.example).
// Prod: `npm run build` emits dist/, served by FastAPI at / when present.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: false,
      },
    },
  },
});
