export type Health = {
  status: string;
  database_ready: boolean;
  mode: "offline";
  offline_import_ready: boolean;
  raw_text_storage: boolean;
  version: string;
  content_detector_enabled?: boolean;
  content_detector_model?: string | null;
  semantic_context_enabled?: boolean;
  semantic_context_model?: string | null;
};
export type OfflineImport = {
  dataset_name: string;
  description: string | null;
  content_origin: string;
  total_events: number;
  created_events: number;
  duplicate_events: number;
  result_post_ids: string[];
  result_alert_ids: string[];
};
export type ContentSignal = {
  source: "experimental_local_model" | "human_review" | "organizer_annotation";
  status: string;
  score?: number;
  category?: string;
  requires_review?: boolean;
  context_score?: number;
  label_scores?: Record<string, number>;
  model_id?: string;
  model_revision?: string;
  threshold?: number;
};
export type ContentReviewEvidence = {
  current: ContentSignal | null;
  experimental_local_model: ContentSignal | null;
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
  content_review_evidence?: ContentReviewEvidence | null;
  priority: "low" | "medium" | "high";
  confidence: string;
  features: Record<string, number | null>;
  explanations: string[];
  status: string;
  resolution: string | null;
  reviewer_note: string | null;
  reviews?: Array<{
    score: number;
    category: string;
    reviewer_note: string | null;
    reviewed_at: string;
  }>;
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
  content_signal?: ContentSignal | null;
  semantic_context?: SemanticContextEvidence | null;
  reply_context?: ReplyContext | null;
  replies?: ThreadEvent[];
};
export type SemanticContextEvidence = {
  source: "experimental_local_semantic_model";
  status: "evaluated" | "unavailable";
  model_id?: string;
  model_revision?: string;
  threshold?: number;
  time_window_seconds?: number;
  neighbor_count?: number;
  strongest_similarity?: number;
  closest_timing_seconds?: number | null;
  shared_parent_match_count?: number;
  reason?: string;
};
export type ReplyContextSignal = {
  source: "deterministic_structure" | "experimental_local_context_model";
  status: string;
  relation?: string;
  score?: number | null;
  relation_scores?: Record<string, number>;
  model_id?: string;
  model_revision?: string;
  requires_human_review?: boolean;
  reason?: string;
};
export type ReplyContext = {
  current: ReplyContextSignal;
  semantic_model: ReplyContextSignal | null;
  parent_available: boolean;
  reply_position: number;
  sibling_count: number;
  exact_duplicate_sibling_count: number;
  near_duplicate_sibling_count: number;
  seconds_after_parent: number | null;
  same_participant_as_parent: boolean | null;
};
export type CoordinationGraphNode = {
  id: string;
  label: string;
  cluster_id: number | null;
  event_count: number;
  reply_count: number;
  connection_count: number;
  average_connection_strength: number;
  context_relations: Record<string, number>;
  first_observed_at: string;
  last_observed_at: string;
};
export type CoordinationGraphEdge = {
  id: string;
  source: string;
  target: string;
  strength: number;
  signals: {
    exact_text: number;
    semantic_context: number;
    timing: number;
    shared_thread: number;
  };
  minimum_gap_seconds: number;
  reasons: string[];
};
export type CoordinationGraphData = {
  nodes: CoordinationGraphNode[];
  edges: CoordinationGraphEdge[];
  summary: {
    participant_count_total: number;
    participant_count_shown: number;
    edge_count: number;
    cluster_count: number;
    strongest_edge: number;
    truncated: boolean;
  };
  method: {
    time_window_seconds: number;
    minimum_edge_strength: number;
    weights: {
      exact_text: number;
      semantic_context: number;
      timing: number;
      shared_thread: number;
    };
    semantic_context_available: boolean;
    safety_statement: string;
  };
};
