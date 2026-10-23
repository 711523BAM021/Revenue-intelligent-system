import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    plugins: [react(), tailwindcss()],
    server: {
      host: "0.0.0.0",
      port: 3000,
      strictPort: true,
      // Host allow-listing is supplied per process (VM preview hostname),
      // never committed as a blanket allow-list.
      allowedHosts: env.VITE_ALLOWED_HOSTS
        ? env.VITE_ALLOWED_HOSTS.split(",").map((h) => h.trim()).filter(Boolean)
        : undefined,
      proxy: {
        "/api": {
          target: env.VITE_API_PROXY || "http://127.0.0.1:8000",
          changeOrigin: true,
        },
      },
    },
    preview: { host: "0.0.0.0", port: 3000 },
  };
});
