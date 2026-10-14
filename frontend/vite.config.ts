/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Em desenvolvimento, /api vai para o FastAPI na porta 8000 (python -m uvicorn api.main:app).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: true } } },
  test: { environment: "node", include: ["src/**/*.test.{ts,tsx}"] },
});
