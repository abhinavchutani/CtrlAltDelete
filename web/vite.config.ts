import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

declare const process: { env: Record<string, string | undefined> };

// `make api` serves on :8000; the dev server proxies /api there (API_MOCK=1 for fixtures).
// Another port: API_URL=http://127.0.0.1:8088 npm run dev
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": process.env.API_URL ?? "http://127.0.0.1:8000" } },
  build: { chunkSizeWarningLimit: 2500 },
});
