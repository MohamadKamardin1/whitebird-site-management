import path from "node:path";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

/**
 * White Bird frontend build configuration.
 * Development serves the React workspace on port 5173 and proxies the Django
 * API; production builds into frontend/dist for collection under /static/frontend/.
 */
export default defineConfig({
  base: "/static/frontend/",
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "client", "src"),
      "@shared": path.resolve(import.meta.dirname, "shared"),
    },
  },
  root: path.resolve(import.meta.dirname, "client"),
  build: {
    outDir: path.resolve(import.meta.dirname, "dist"),
    emptyOutDir: true,
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: process.env.VITE_DJANGO_ORIGIN || "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
