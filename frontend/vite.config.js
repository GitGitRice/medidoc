import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: (process.env.VITE_ALLOWED_HOST ?? "localhost").split(","),
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.js",
  },
});
