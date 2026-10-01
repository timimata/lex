import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// In development the API runs separately: python -m lex.api --demo
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
});
