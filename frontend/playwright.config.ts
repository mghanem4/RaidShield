import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  use: { baseURL: "http://127.0.0.1:5174" },
  webServer: [
    {
      command:
        "cd ../backend && ../.venv/bin/alembic upgrade head && ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010",
      url: "http://127.0.0.1:8010/api/v1/health",
      reuseExistingServer: false,
      env: {
        ...process.env,
        APP_ENV: "test",
        ADMIN_TOKEN: "test-admin-token",
        PSEUDONYMIZATION_KEY: "e2e-pseudonym-key",
        DATABASE_URL: "sqlite:///./data/e2e.db",
        FRONTEND_ORIGIN: "http://127.0.0.1:5174",
        STORE_RAW_TEXT: "false",
        CONTENT_DETECTOR_ENABLED: "false",
        SEMANTIC_CONTEXT_ENABLED: "false",
      },
    },
    {
      command: "npm run dev -- --port 5174 --config vite.e2e.config.ts",
      url: "http://127.0.0.1:5174",
      reuseExistingServer: false,
    },
  ],
});
