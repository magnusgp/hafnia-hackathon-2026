import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: "127.0.0.1",
    port: 4174,
    strictPort: true,
    proxy: { "/api": { target: "http://127.0.0.1:8765", changeOrigin: true } },
    fs: { deny: ["**/public/private/**", "**/.env*", "**/*.{crt,pem}"] },
  },
  // Private evidence is served only by Python, never copied into public build output.
  publicDir: false,
});
