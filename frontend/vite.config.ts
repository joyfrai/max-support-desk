import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: "src/main.tsx",
      output: {
        entryFileNames: "support-desk.js",
        chunkFileNames: "support-desk-[hash].js",
        assetFileNames: "support-desk.[ext]"
      }
    }
  }
});

