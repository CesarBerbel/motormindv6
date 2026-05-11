import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

function vendorChunk(id) {
  if (!id.includes("node_modules")) return undefined;

  if (id.includes("react-quill") || id.includes("quill") || id.includes("parchment")) {
    return "vendor-editor";
  }

  return "vendor";
}

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks: vendorChunk,
      },
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/media": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
