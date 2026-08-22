import { test, expect } from "@playwright/test";
test("replay, inspect, resolve, and export reply-thread alert", async ({
  page,
}) => {
  page.on("pageerror", (error) =>
    console.error("Browser page error:", error.message),
  );
  page.on("console", (message) => {
    if (message.type() === "error")
      console.error("Browser console error:", message.text());
  });
  await page.goto("/test-lab");
  await page.screenshot({ path: "test-results/test-lab.png", fullPage: true });
  await page.getByLabel("Local administrator token").fill("test-admin-token");
  await page.getByLabel("Safe fixture").selectOption("reply_thread_burst");
  await page
    .getByRole("button", { name: "Reset and replay immediately" })
    .click();
  await expect(page.getByText("13 of 13 events processed")).toBeVisible();
  await page.getByRole("link", { name: "Open generated alert" }).click();
  await expect(
    page.getByText(/activity was concentrated in one thread/i),
  ).toBeVisible();
  await expect(page.getByText("Reply-thread evidence")).toBeVisible();
  await page.screenshot({
    path: "test-results/alert-detail.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Mark benign coordination" }).click();
  await expect(page.getByText("resolved")).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export redacted evidence" }).click();
  await download;
  await page.goto("/");
  await expect(page.getByText("Monitored posts")).toBeVisible();
  await page.screenshot({ path: "test-results/dashboard.png", fullPage: true });
  await page.locator(".post-card").first().click();
  await expect(page.getByText("Reply relationships")).toBeVisible();
  await page.screenshot({
    path: "test-results/post-detail.png",
    fullPage: true,
  });
  await page.goto("/settings");
  await page.screenshot({ path: "test-results/settings.png", fullPage: true });
  await page.goto("/safety");
  await page.screenshot({ path: "test-results/safety.png", fullPage: true });
});
