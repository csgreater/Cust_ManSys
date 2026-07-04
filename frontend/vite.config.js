import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  base: "/ui/",
  plugins: [vue()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/orders/export": "http://127.0.0.1:8000"
    }
  },
  build: {
    outDir: "dist",
    emptyOutDir: true
  }
});
