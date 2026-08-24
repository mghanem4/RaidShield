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
  const offlineDataset = {
    dataset_name: "e2e_safe_batch",
    description: "Synthetic safe offline import for browser validation.",
    content_origin: "synthetic-safe-placeholder",
    events: Array.from({ length: 4 }, (_, index) => ({
      source_event_id: `e2e-offline-${index}`,
      post_id: "e2e-offline-post",
      comment_id: `e2e-offline-comment-${index}`,
      parent_id: "e2e-offline-parent",
      participant_id: `e2e-offline-participant-${index}`,
      occurred_at: `2026-08-24T12:00:0${index * 2}Z`,
      text: "PATTERN_OFFLINE_REVIEW",
    })),
  };
  await page.getByLabel("Offline JSON dataset").setInputFiles({
    name: "e2e-safe-batch.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify(offlineDataset)),
  });
  await page.getByRole("button", { name: "Import offline dataset" }).click();
  await expect(page.getByText("4 of 4 events imported")).toBeVisible();
  await page.screenshot({
    path: "test-results/offline-import.png",
    fullPage: true,
  });
  await page.getByLabel("Safe fixture").selectOption("reply_thread_burst");
  await page
    .getByRole("button", { name: "Reset and replay immediately" })
    .click();
  await expect(page.getByText("13 of 13 events processed")).toBeVisible();
  await page.getByRole("link", { name: "Open generated alert" }).click();
  await expect(
    page.getByText(/activity was concentrated in one thread/i),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Coordination graph" }),
  ).toBeVisible();
  await expect(
    page.getByLabel("Interactive participant coordination graph"),
  ).toBeVisible();
  await page.getByRole("button", { name: "Arrange nodes" }).click();
  const movableGraph = page.getByLabel(
    "Movable pseudonymous participant graph",
  );
  const graphNode = movableGraph.getByRole("button").first();
  const nodeCircle = graphNode.locator("circle").first();
  const initialX = await nodeCircle.getAttribute("cx");
  const nodeBox = await nodeCircle.boundingBox();
  if (!nodeBox) throw new Error("Graph node was not measurable");
  await nodeCircle.hover({ force: true });
  await page.mouse.down();
  await expect(
    page.getByLabel("Interactive participant coordination graph"),
  ).toHaveClass(/node/);
  await page.mouse.move(
    nodeBox.x + nodeBox.width / 2 + 55,
    nodeBox.y + nodeBox.height / 2 + 30,
    { steps: 4 },
  );
  await page.mouse.up();
  await expect(page.getByText("Position pinned")).toBeVisible();
  await expect.poll(() => nodeCircle.getAttribute("cx")).not.toBe(initialX);
  await page.getByRole("button", { name: "Zoom in" }).click();
  await expect(page.getByLabel("Current zoom")).toHaveText("120%");
  await page.screenshot({
    path: "test-results/graph-interaction.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Reset layout" }).click();
  await expect(page.getByLabel("Current zoom")).toHaveText("100%");
  await expect(page.getByText("Reply-thread evidence")).toBeVisible();
  const replyContext = page
    .getByText("Context: repeated with siblings")
    .first();
  await expect(replyContext).toBeVisible();
  await replyContext.click();
  await expect(page.getByText("Exact sibling repeats").first()).toBeVisible();
  await page.getByLabel("Review category").selectOption("no_concern");
  await page.getByLabel(/Review score/).fill("0.2");
  await page
    .getByLabel("Reviewer note")
    .fill("Controlled fixture reviewed as safe context.");
  await page.getByRole("button", { name: "Save human content review" }).click();
  await expect(page.getByText("Human content review saved.")).toBeVisible();
  await expect(
    page.getByText("Human content review", { exact: true }),
  ).toBeVisible();
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
  await expect(
    page.getByRole("heading", { name: "Imported posts" }),
  ).toBeVisible();
  await page.screenshot({ path: "test-results/dashboard.png", fullPage: true });
  await page.locator(".post-card").first().click();
  await expect(page.getByText("Reply relationships")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Coordination graph" }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/post-detail.png",
    fullPage: true,
  });
  await page.goto("/settings");
  await page.screenshot({ path: "test-results/settings.png", fullPage: true });
  await page.goto("/safety");
  await page.screenshot({ path: "test-results/safety.png", fullPage: true });
});
