import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const allowedHosts = process.env.VITE_ALLOWED_HOSTS?.split(",")
  .map((host) => host.trim())
  .filter(Boolean);

export default defineConfig({
  plugins: [react()],
  server: {
    ...(allowedHosts?.length ? { allowedHosts } : {}),
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.js",
  },
});
