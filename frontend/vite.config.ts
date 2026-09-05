import release from "../backend/soj_shared/version.json" with { type: "json" };
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  define: { __APP_VERSION__: JSON.stringify(release.version) },
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/setupTests.js",
  },
});
