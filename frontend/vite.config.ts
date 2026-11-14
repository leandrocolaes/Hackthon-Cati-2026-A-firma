import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Só vale no modo desenvolvimento (npm run dev, porta 5173).
// Faz o mesmo papel do Nginx: manda /api para o backend rodando em localhost:8000.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": { target: "http://localhost:8000", ws: true },
    },
  },
});
