import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

const projectRoot = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig({
  root: `${projectRoot}web`,
  plugins: [react()],
  build: {
    outDir: `${projectRoot}dist/web`,
    emptyOutDir: true,
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8787",
        changeOrigin: false,
        ws: true,
      },
      "/browser": {
        target: "http://127.0.0.1:8787",
        changeOrigin: false,
        ws: true,
      },
      "/terminal": {
        target: "http://127.0.0.1:8787",
        changeOrigin: false,
        ws: true,
      },
      "/hermes": {
        target: "http://127.0.0.1:8787",
        changeOrigin: false,
        ws: true,
      },
      "/openclaw": {
        target: "http://127.0.0.1:8787",
        changeOrigin: false,
        ws: true,
      },
    },
  },
});
