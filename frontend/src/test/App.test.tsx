import { cleanup, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App";

const renderApp = (path = "/") =>
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("RaidShield UI", () => {
  it("renders dashboard empty state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        Promise.resolve(
          new Response(
            JSON.stringify(
              url.includes("health")
                ? {
                    status: "ok",
                    database_ready: true,
                    mode: "replay",
                    meta_configured: false,
                  }
                : [],
            ),
            { status: 200 },
          ),
        ),
      ),
    );
    renderApp();
    expect(await screen.findByText("No activity yet")).toBeInTheDocument();
    expect(screen.getByText(/do not prove intent/i)).toBeInTheDocument();
  });
  it("renders replay activity and separate scores", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        Promise.resolve(
          new Response(
            JSON.stringify(
              url.includes("/alerts/")
                ? {
                    id: "a",
                    post_id: "p",
                    parent_thread_id: null,
                    created_at: "2026-01-01",
                    window_start: "2026-01-01",
                    window_end: "2026-01-01",
                    coordination_score: 0.82,
                    content_review_score: 0.4,
                    priority: "medium",
                    confidence: "medium",
                    features: { burst: 0.9 },
                    explanations: ["Six participants engaged."],
                    status: "new",
                    resolution: null,
                    reviewer_note: null,
                  }
                : url.includes("/threads")
                  ? { threads: [], unknown_parent_replies: [] }
                  : {
                      status: "ok",
                      database_ready: true,
                      mode: "replay",
                      meta_configured: false,
                    },
            ),
            { status: 200 },
          ),
        ),
      ),
    );
    renderApp("/alerts/a");
    expect(
      await screen.findByText("Coordination indicators"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Human / organizer content review"),
    ).toBeInTheDocument();
    expect(screen.getAllByText(/do not prove intent/i).length).toBeGreaterThan(
      0,
    );
  });
  it("renders reply parent and children", async () => {
    const post = {
      id: "p",
      source: "replay",
      source_post_id: "demo",
      display_label: "Protected post",
      last_event_at: "2026-01-01",
      comment_count: 1,
      reply_count: 1,
      alert_count: 0,
      unique_participants: 2,
      alerts: [],
    };
    const threads = {
      threads: [
        {
          id: "1",
          comment_id: "root",
          parent_id: null,
          participant: "Participant AAAA",
          occurred_at: "2026-01-01",
          content: "content hidden",
          replies: [
            {
              id: "2",
              comment_id: "reply",
              parent_id: "root",
              participant: "Participant BBBB",
              occurred_at: "2026-01-01",
              content: "content hidden",
            },
          ],
        },
      ],
      unknown_parent_replies: [],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        Promise.resolve(
          new Response(
            JSON.stringify(url.includes("threads") ? threads : post),
            { status: 200 },
          ),
        ),
      ),
    );
    renderApp("/posts/p");
    expect(await screen.findByText("Participant AAAA")).toBeInTheDocument();
    expect(screen.getByText("Participant BBBB")).toBeInTheDocument();
  });
});
