import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  // Electron production loads UI from file://.../dist/index.html
  // so assets must be relative paths instead of root-absolute /assets/*
  base: "./",
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true
  }
});
