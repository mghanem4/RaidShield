import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  use: { baseURL: "http://127.0.0.1:5173" },
  webServer: [
    {
      command:
        "cd ../backend && ../.venv/bin/alembic upgrade head && ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000",
      url: "http://127.0.0.1:8000/api/v1/health",
      reuseExistingServer: true,
      env: {
        ...process.env,
        APP_ENV: "test",
        ADMIN_TOKEN: "test-admin-token",
        PSEUDONYMIZATION_KEY: "e2e-pseudonym-key",
        DATABASE_URL: "sqlite:///./data/e2e.db",
      },
    },
    {
      command: "npm run dev",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: true,
    },
  ],
});
