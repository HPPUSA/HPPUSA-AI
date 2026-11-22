import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  testMatch: "frontend_browser.spec.mjs",
  timeout: 30_000,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:8765",
    headless: true
  },
  webServer: {
    command: "python -m flask --app App run --host 127.0.0.1 --port 8765 --no-reload",
    url: "http://127.0.0.1:8765/",
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
    env: {
      GROQ_API_KEY: "",
      HPPUSA_ORIGIN_AUTH_TOKEN: "browser-ci-only-placeholder"
    }
  }
});
