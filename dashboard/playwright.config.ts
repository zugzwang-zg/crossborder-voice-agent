import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  use: { baseURL: "http://127.0.0.1:4174", viewport: { width: 1440, height: 1000 }, trace: "retain-on-failure" },
  webServer: { command: "pnpm exec vinext dev --hostname 127.0.0.1 --port 4174", url: "http://127.0.0.1:4174", reuseExistingServer: false, timeout: 120000 },
});
