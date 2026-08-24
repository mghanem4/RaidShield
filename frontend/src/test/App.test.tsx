import { cleanup, fireEvent, render, screen } from "@testing-library/react";
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

const graph = {
  nodes: [
    {
      id: "participant-001",
      label: "Participant AAAA",
      cluster_id: 1,
      event_count: 2,
      reply_count: 1,
      connection_count: 1,
      average_connection_strength: 0.92,
      context_relations: { repeated_with_siblings: 1 },
      first_observed_at: "2026-01-01T00:00:00Z",
      last_observed_at: "2026-01-01T00:00:02Z",
    },
    {
      id: "participant-002",
      label: "Participant BBBB",
      cluster_id: 1,
      event_count: 1,
      reply_count: 1,
      connection_count: 1,
      average_connection_strength: 0.92,
      context_relations: { opposes_parent: 1 },
      first_observed_at: "2026-01-01T00:00:01Z",
      last_observed_at: "2026-01-01T00:00:01Z",
    },
  ],
  edges: [
    {
      id: "edge-0001",
      source: "participant-001",
      target: "participant-002",
      strength: 0.92,
      signals: {
        exact_text: 1,
        semantic_context: 0.86,
        timing: 0.9,
        shared_thread: 1,
      },
      minimum_gap_seconds: 1,
      reasons: [
        "exact repeated text",
        "activity within 1 seconds",
        "shared reply target",
      ],
    },
  ],
  summary: {
    participant_count_total: 2,
    participant_count_shown: 2,
    edge_count: 1,
    cluster_count: 1,
    strongest_edge: 0.92,
    truncated: false,
  },
  method: {
    time_window_seconds: 30,
    minimum_edge_strength: 0.25,
    weights: {
      exact_text: 0.25,
      semantic_context: 0.3,
      timing: 0.3,
      shared_thread: 0.15,
    },
    semantic_context_available: true,
    safety_statement:
      "Connections are behavioral indicators for human review and do not prove automation, intent, identity, or a policy violation.",
  },
};

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
                    mode: "offline",
                    offline_import_ready: true,
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
              url.includes("coordination-graph")
                ? graph
                : url.includes("/alerts/")
                  ? {
                      id: "a",
                      post_id: "p",
                      parent_thread_id: null,
                      created_at: "2026-01-01",
                      window_start: "2026-01-01",
                      window_end: "2026-01-01",
                      coordination_score: 0.82,
                      content_review_score: 0.4,
                      content_review_evidence: {
                        current: {
                          source: "experimental_local_model",
                          status: "experimental",
                          score: 0.4,
                          category: "direct_insult",
                        },
                        experimental_local_model: {
                          source: "experimental_local_model",
                          status: "experimental",
                          score: 0.4,
                          category: "direct_insult",
                          context_score: 0.6,
                          label_scores: { direct_insult: 0.4 },
                          model_id: "local-test-model",
                          model_revision: "test-revision",
                        },
                      },
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
                        mode: "offline",
                        offline_import_ready: true,
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
    expect(screen.getByText("Experimental content signal")).toBeInTheDocument();
    expect(
      screen.getByText("Potential content-review need"),
    ).toBeInTheDocument();
    expect(screen.getByText("Review observed content")).toBeInTheDocument();
    expect(screen.getByText("Coordination graph")).toBeInTheDocument();
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
              content_signal: {
                source: "experimental_local_model",
                status: "experimental",
                score: 0.76,
                category: "direct_insult",
                requires_review: true,
                context_score: 0.21,
                label_scores: {
                  direct_insult: 0.76,
                  targeted_hostility: 0.43,
                  threat_or_harm: 0.12,
                },
                model_id: "local-test-model",
                model_revision: "test-revision",
                threshold: 0.65,
              },
              semantic_context: {
                source: "experimental_local_semantic_model",
                status: "evaluated",
                model_id: "local-semantic-test-model",
                model_revision: "semantic-test-revision",
                threshold: 0.78,
                time_window_seconds: 60,
                neighbor_count: 2,
                strongest_similarity: 0.86,
                closest_timing_seconds: 4,
                shared_parent_match_count: 1,
              },
              reply_context: {
                current: {
                  source: "deterministic_structure",
                  status: "structural_only",
                  relation: "repeated_with_siblings",
                  score: 1,
                },
                semantic_model: null,
                parent_available: true,
                reply_position: 1,
                sibling_count: 1,
                exact_duplicate_sibling_count: 1,
                near_duplicate_sibling_count: 0,
                seconds_after_parent: 2,
                same_participant_as_parent: false,
              },
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
            JSON.stringify(
              url.includes("coordination-graph")
                ? graph
                : url.includes("threads")
                  ? threads
                  : post,
            ),
            { status: 200 },
          ),
        ),
      ),
    );
    renderApp("/posts/p");
    expect(
      (await screen.findAllByText("Participant AAAA")).length,
    ).toBeGreaterThan(0);
    expect(screen.getAllByText("Participant BBBB").length).toBeGreaterThan(0);
    expect(screen.getByText("Coordination graph")).toBeInTheDocument();
    expect(
      (await screen.findAllByText(/exact repeated text/)).length,
    ).toBeGreaterThan(0);
    expect(
      screen.getByText("Context: repeated with siblings"),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByText("Flagged for human review"));
    expect(
      screen.getByText(/direct insult was the highest-ranked label at 76%/i),
    ).toBeInTheDocument();
    expect(screen.getByText("Complete label rankings")).toBeInTheDocument();
    expect(screen.getByText("Parent message")).toBeInTheDocument();
    expect(screen.getByText("threat or harm ranking")).toBeInTheDocument();
    expect(screen.getByText(/Sibling comparison: 1 exact/)).toBeInTheDocument();
    expect(
      screen.getByText(/not the model’s hidden reasoning/i),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByText("2 semantic-context matches"));
    expect(screen.getByText("86% ranking")).toBeInTheDocument();
    expect(
      screen.getByText(/as close as 4 seconds apart/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/requires corroborating timing or thread evidence/i),
    ).toBeInTheDocument();
    expect(screen.getByText("Reply context")).toBeInTheDocument();
    const graphNode = screen.getByRole("button", {
      name: /Participant AAAA, 1 connections/,
    });
    fireEvent.keyDown(graphNode, { key: "ArrowRight" });
    expect(await screen.findByText("Position pinned")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Zoom in" }));
    expect(screen.getByLabelText("Current zoom")).toHaveTextContent("120%");
    fireEvent.click(screen.getByRole("button", { name: "Reset layout" }));
    expect(screen.getByLabelText("Current zoom")).toHaveTextContent("100%");
  });
});
