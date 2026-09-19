import { resolve } from "node:path";
import { defineConfig } from "vite";

// Keep the existing HTML pages while producing one deployable dist/ directory.
export default defineConfig({
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        home: resolve(import.meta.dirname, "index.html"),
        app: resolve(import.meta.dirname, "app.html"),
        login: resolve(import.meta.dirname, "login.html"),
        signup: resolve(import.meta.dirname, "signup.html"),
      },
    },
  },
});
