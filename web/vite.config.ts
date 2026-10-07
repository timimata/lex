import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The components are written against React's API and type-checked with its types; the bundle
// runs them on Preact's compatibility layer, a fraction of React's size (web/ROADMAP.md, stage 7).
const preact = {
  react: "preact/compat",
  "react-dom/client": "preact/compat/client",
  "react-dom": "preact/compat",
  "react/jsx-runtime": "preact/jsx-runtime",
  "react/jsx-dev-runtime": "preact/jsx-dev-runtime",
};

// In development the API runs separately: python -m lex.api --demo
export default defineConfig({
  plugins: [react()],
  resolve: { alias: preact },
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
});
