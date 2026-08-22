export type Health = {
  status: string;
  database_ready: boolean;
  mode: "replay" | "instagram";
  meta_configured: boolean;
  raw_text_storage: boolean;
  version: string;
};
export type Post = {
  id: string;
  source: string;
  source_post_id: string;
  display_label: string;
  last_event_at: string;
  comment_count: number;
  reply_count: number;
  alert_count: number;
  unique_participants?: number;
  alerts?: Alert[];
};
export type Alert = {
  id: string;
  post_id: string;
  parent_thread_id: string | null;
  created_at: string;
  window_start: string;
  window_end: string;
  coordination_score: number;
  content_review_score: number | null;
  priority: "low" | "medium" | "high";
  confidence: string;
  features: Record<string, number>;
  explanations: string[];
  status: string;
  resolution: string | null;
  reviewer_note: string | null;
};
export type Fixture = {
  fixture_name: string;
  description: string;
  content_origin: string;
  expected_outcome: { coordination_alert: boolean; high_priority: boolean };
};
export type Replay = {
  id: string;
  fixture: string;
  status: string;
  total_events: number;
  processed_events: number;
  result_post_id: string | null;
  result_alert_id: string | null;
};
export type ThreadEvent = {
  id: string;
  comment_id: string;
  parent_id: string | null;
  participant: string;
  occurred_at: string;
  content: string;
  replies?: ThreadEvent[];
};
