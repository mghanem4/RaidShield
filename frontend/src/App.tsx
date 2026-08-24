import { useEffect, useState } from "react";
import {
  Link,
  NavLink,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams,
} from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import type { Alert, ContentSignal, ThreadEvent } from "./types";
import CoordinationGraph from "./CoordinationGraph";

const SafetyNotice = () => (
  <aside className="notice" aria-label="Safety notice">
    <span>Human review required</span> Signals prioritize human review; they do
    not prove intent or a policy violation.
  </aside>
);
const Score = ({ label, value }: { label: string; value: number | null }) => (
  <div className="score">
    <div>
      <span>{label}</span>
      <strong>
        {value === null ? "Not provided" : `${Math.round(value * 100)}%`}
      </strong>
    </div>
    {value !== null && (
      <div
        className="track"
        role="meter"
        aria-label={label}
        aria-valuenow={Math.round(value * 100)}
      >
        <i style={{ width: `${value * 100}%` }} />
      </div>
    )}
  </div>
);
const Empty = ({ title, body }: { title: string; body: string }) => (
  <div className="empty">
    <div className="empty-icon">◎</div>
    <h2>{title}</h2>
    <p>{body}</p>
    <Link className="button" to="/test-lab">
      Open Test Lab
    </Link>
  </div>
);
const ErrorBox = ({ error }: { error: Error }) => (
  <p className="error" role="alert">
    {error.message}
  </p>
);

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [pathname]);
  return null;
}

function Dashboard() {
  const health = useQuery({ queryKey: ["health"], queryFn: api.health });
  const posts = useQuery({ queryKey: ["posts"], queryFn: api.posts });
  const alerts = useQuery({ queryKey: ["alerts"], queryFn: api.alerts });
  if (posts.error) return <ErrorBox error={posts.error} />;
  const items = posts.data ?? [];
  const recentAlerts = alerts.data ?? [];
  return (
    <main>
      <div className="hero">
        <div>
          <p className="eyebrow">Offline review surface</p>
          <h1>Activity overview</h1>
          <p>
            Explainable group-level indicators from authorized local datasets.
          </p>
        </div>
        <div className="mode">
          <i className={health.data?.database_ready ? "online" : ""} />
          <span>{health.data?.mode ?? "checking"} mode</span>
          <small>
            {health.data?.offline_import_ready
              ? "Local JSON import ready"
              : "Checking local import"}
          </small>
        </div>
      </div>
      <SafetyNotice />
      <section className="stats">
        <article>
          <span>Events observed</span>
          <strong>
            {items.reduce((n, p) => n + p.comment_count + p.reply_count, 0)}
          </strong>
        </article>
        <article>
          <span>Active alerts</span>
          <strong>
            {
              recentAlerts.filter(
                (a) => a.status !== "resolved" && a.status !== "dismissed",
              ).length
            }
          </strong>
        </article>
        <article>
          <span>Imported posts</span>
          <strong>{items.length}</strong>
        </article>
        <article>
          <span>High priority</span>
          <strong>
            {recentAlerts.filter((a) => a.priority === "high").length}
          </strong>
        </article>
      </section>
      <section className="section-head">
        <div>
          <p className="eyebrow">Recent datasets</p>
          <h2>Imported posts</h2>
        </div>
        <Link to="/test-lab">Run a safe replay →</Link>
      </section>
      {items.length === 0 ? (
        <Empty
          title="No activity yet"
          body="Use a bundled synthetic fixture to see how indicators and reply threads are presented."
        />
      ) : (
        <div className="grid">
          {items.map((post) => (
            <Link
              className="card post-card"
              to={`/posts/${post.id}`}
              key={post.id}
            >
              <span className="pill">{post.source}</span>
              <h3>{post.display_label}</h3>
              <p>
                {post.comment_count} top-level · {post.reply_count} replies
              </p>
              <footer>
                <span>
                  {post.alert_count} alert{post.alert_count === 1 ? "" : "s"}
                </span>
                <time>{new Date(post.last_event_at).toLocaleString()}</time>
              </footer>
            </Link>
          ))}
        </div>
      )}
    </main>
  );
}

function AlertCard({ alert }: { alert: Alert }) {
  return (
    <Link className="card alert-card" to={`/alerts/${alert.id}`}>
      <div>
        <span className={`pill ${alert.priority}`}>
          {alert.priority} priority
        </span>
        <span className="muted">{alert.confidence} data confidence</span>
      </div>
      <h3>Possible coordinated activity</h3>
      <div className="dual">
        <Score label="Coordination" value={alert.coordination_score} />
        <Score label="Content review" value={alert.content_review_score} />
      </div>
      <p>{alert.explanations[0]}</p>
    </Link>
  );
}
function PostPage({ token }: { token: string }) {
  const { id = "" } = useParams();
  const post = useQuery({
    queryKey: ["post", id],
    queryFn: () => api.post(id),
  });
  const threads = useQuery({
    queryKey: ["threads", id, Boolean(token)],
    queryFn: () => api.threads(id, token),
  });
  if (post.error) return <ErrorBox error={post.error} />;
  if (!post.data)
    return (
      <main>
        <p>Loading…</p>
      </main>
    );
  return (
    <main>
      <Link className="back" to="/">
        ← Dashboard
      </Link>
      <div className="hero compact">
        <div>
          <p className="eyebrow">Post detail</p>
          <h1>{post.data.display_label}</h1>
          <p>
            {post.data.comment_count} top-level comments ·{" "}
            {post.data.reply_count} replies · {post.data.unique_participants}{" "}
            participants
          </p>
        </div>
      </div>
      <SafetyNotice />
      <section className="section-head">
        <h2>Relevant alerts</h2>
      </section>
      {post.data.alerts?.length ? (
        <div className="grid">
          {post.data.alerts.map((a) => (
            <AlertCard key={a.id} alert={a} />
          ))}
        </div>
      ) : (
        <p className="muted">No coordination alert for this post.</p>
      )}
      <section className="section-head">
        <div>
          <p className="eyebrow">Explainable clusters</p>
          <h2>Participant relationships</h2>
        </div>
      </section>
      <CoordinationGraph postId={id} />
      <section className="section-head">
        <div>
          <p className="eyebrow">Reply relationships</p>
          <h2>Threads</h2>
        </div>
      </section>
      <ThreadList
        threads={threads.data?.threads ?? []}
        unknown={threads.data?.unknown_parent_replies ?? []}
      />
    </main>
  );
}
function ThreadList({
  threads,
  unknown = [],
}: {
  threads: ThreadEvent[];
  unknown?: ThreadEvent[];
}) {
  if (!threads.length && !unknown.length)
    return <p className="muted">No reply relationships observed.</p>;
  return (
    <div className="threads">
      {threads.map((root) => (
        <article className="thread" key={root.id}>
          <div className="thread-root">
            <strong>{root.participant}</strong>
            <time>{new Date(root.occurred_at).toLocaleTimeString()}</time>
            <p>{root.content}</p>
            <ContentEvidence event={root} />
            <SemanticCoordinationEvidence event={root} />
          </div>
          <div
            className="replies"
            aria-label={`Replies to ${root.participant}`}
          >
            {root.replies?.map((reply) => (
              <div key={reply.id}>
                <strong>{reply.participant}</strong>
                <time>{new Date(reply.occurred_at).toLocaleTimeString()}</time>
                <p>{reply.content}</p>
                <ContentEvidence event={reply} parent={root} />
                <SemanticCoordinationEvidence event={reply} />
                {reply.reply_context && (
                  <details className="reply-context">
                    <summary>
                      Context:{" "}
                      {formatRelation(reply.reply_context.current.relation)}
                    </summary>
                    <dl>
                      <div>
                        <dt>Reply position</dt>
                        <dd>
                          {reply.reply_context.reply_position} of{" "}
                          {reply.reply_context.sibling_count + 1}
                        </dd>
                      </div>
                      <div>
                        <dt>After parent</dt>
                        <dd>
                          {reply.reply_context.seconds_after_parent === null
                            ? "Unknown"
                            : `${reply.reply_context.seconds_after_parent}s`}
                        </dd>
                      </div>
                      <div>
                        <dt>Exact sibling repeats</dt>
                        <dd>
                          {reply.reply_context.exact_duplicate_sibling_count}
                        </dd>
                      </div>
                      <div>
                        <dt>Near sibling repeats</dt>
                        <dd>
                          {reply.reply_context.near_duplicate_sibling_count}
                        </dd>
                      </div>
                    </dl>
                    {reply.reply_context.current.source ===
                      "experimental_local_context_model" && (
                      <p>
                        Experimental relationship ranking:{" "}
                        {Math.round(
                          (reply.reply_context.current.score ?? 0) * 100,
                        )}
                        %
                      </p>
                    )}
                    <p className="hint">
                      Context signals require human interpretation and do not
                      prove agreement, intent, or authorship.
                    </p>
                  </details>
                )}
              </div>
            ))}
          </div>
        </article>
      ))}
      {unknown.length > 0 && (
        <article className="thread">
          <h3>Unknown or unavailable parent</h3>
          {unknown.map((x) => (
            <div key={x.id}>
              <p>
                {x.participant} · {x.content}
              </p>
              <ContentEvidence event={x} />
              <SemanticCoordinationEvidence event={x} />
            </div>
          ))}
        </article>
      )}
    </div>
  );
}

function formatRelation(relation?: string) {
  if (!relation) return "not evaluated";
  return relation.replaceAll("_", " ");
}

function signalExplanation(signal: ContentSignal) {
  if (signal.status === "unavailable") {
    return "The local model was unavailable, so no ranking was produced.";
  }
  const category = formatRelation(signal.category);
  if (typeof signal.score !== "number") {
    return "The comment was evaluated, but no usable ranking score was returned.";
  }
  const score = `${Math.round(signal.score * 100)}%`;
  if (typeof signal.threshold !== "number") {
    return `${category} was the highest-ranked review label at ${score}.`;
  }
  const threshold = `${Math.round(signal.threshold * 100)}%`;
  return signal.requires_review
    ? `Flagged for human review because ${category} was the highest-ranked label at ${score}, meeting the configured ${threshold} threshold.`
    : `Evaluated but not flagged: ${category} was highest-ranked at ${score}, below the configured ${threshold} threshold.`;
}

function ContentEvidence({
  event,
  parent,
}: {
  event: ThreadEvent;
  parent?: ThreadEvent;
}) {
  const signal = event.content_signal;
  if (!signal) return null;
  const rankings = Object.entries(signal.label_scores ?? {}).sort(
    ([, left], [, right]) => right - left,
  );
  return (
    <details
      className={`content-evidence ${signal.requires_review ? "flagged" : ""}`}
    >
      <summary>
        <span>
          {signal.requires_review
            ? "Flagged for human review"
            : "Model review evidence"}
        </span>
        {typeof signal.score === "number" && (
          <strong>{Math.round(signal.score * 100)}% ranking</strong>
        )}
      </summary>
      <div className="content-evidence-body">
        <p className="calculation-summary">{signalExplanation(signal)}</p>
        <div className="evaluated-context">
          <section>
            <h4>Comment evaluated</h4>
            <blockquote>{event.content}</blockquote>
          </section>
          {parent && (
            <section>
              <h4>Parent message</h4>
              <blockquote>{parent.content}</blockquote>
            </section>
          )}
        </div>
        {rankings.length > 0 && (
          <section className="ranking-list" aria-label="Model label rankings">
            <h4>Complete label rankings</h4>
            {rankings.map(([label, score]) => (
              <Score
                key={label}
                label={`${formatRelation(label)} ranking`}
                value={score}
              />
            ))}
            {typeof signal.context_score === "number" && (
              <Score
                label="Context uncertainty ranking"
                value={signal.context_score}
              />
            )}
          </section>
        )}
        {event.reply_context && (
          <p className="repetition-evidence">
            Sibling comparison:{" "}
            {event.reply_context.exact_duplicate_sibling_count} exact and{" "}
            {event.reply_context.near_duplicate_sibling_count} near repetitions;
            reply {event.reply_context.reply_position} of{" "}
            {event.reply_context.sibling_count + 1}.
          </p>
        )}
        <p className="hint">
          This template describes the output comparison—not the model’s hidden
          reasoning. Rankings are uncalibrated review aids, not probabilities or
          determinations of hate, harm, intent, or a policy violation.
        </p>
        <p className="model-provenance">
          Model: {signal.model_id ?? "local model"} · threshold{" "}
          {typeof signal.threshold === "number"
            ? `${Math.round(signal.threshold * 100)}%`
            : "not available"}
          {signal.model_revision
            ? ` · revision ${signal.model_revision.slice(0, 10)}`
            : ""}
        </p>
      </div>
    </details>
  );
}

function SemanticCoordinationEvidence({ event }: { event: ThreadEvent }) {
  const evidence = event.semantic_context;
  if (!evidence) return null;
  if (evidence.status === "unavailable") {
    return (
      <p className="semantic-context-unavailable">
        Semantic-context comparison unavailable for this import.
      </p>
    );
  }
  const matches = evidence.neighbor_count ?? 0;
  return (
    <details className="semantic-context-evidence">
      <summary>
        <span>
          {matches
            ? `${matches} semantic-context match${matches === 1 ? "" : "es"}`
            : "No semantic-context matches"}
        </span>
        {matches > 0 && typeof evidence.strongest_similarity === "number" && (
          <strong>
            {Math.round(evidence.strongest_similarity * 100)}% ranking
          </strong>
        )}
      </summary>
      <div>
        {matches > 0 ? (
          <p>
            Similar meaning and conversation context were observed with other
            participants
            {typeof evidence.closest_timing_seconds === "number"
              ? ` as close as ${evidence.closest_timing_seconds} seconds apart`
              : ""}
            . {evidence.shared_parent_match_count ?? 0} match
            {(evidence.shared_parent_match_count ?? 0) === 1 ? "" : "es"} shared
            the same direct parent.
          </p>
        ) : (
          <p>
            No different-participant comment exceeded the configured semantic
            threshold within the timing window and matching reply role.
          </p>
        )}
        <p className="hint">
          This experimental indicator can confuse common reactions,
          counterspeech, quotation, or sarcasm. It requires corroborating timing
          or thread evidence and human review.
        </p>
        <p className="model-provenance">
          Model: {evidence.model_id ?? "local semantic model"} · threshold{" "}
          {typeof evidence.threshold === "number"
            ? `${Math.round(evidence.threshold * 100)}%`
            : "not available"}
          {evidence.model_revision
            ? ` · revision ${evidence.model_revision.slice(0, 10)}`
            : ""}
        </p>
      </div>
    </details>
  );
}

function AlertPage({ token }: { token: string }) {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [reviewScore, setReviewScore] = useState(0.5);
  const [reviewCategory, setReviewCategory] = useState("context_needed");
  const [reviewerNote, setReviewerNote] = useState("");
  const alert = useQuery({
    queryKey: ["alert", id],
    queryFn: () => api.alert(id),
  });
  const threads = useQuery({
    queryKey: ["alertThreads", alert.data?.post_id, Boolean(token)],
    queryFn: () => api.threads(alert.data!.post_id, token),
    enabled: !!alert.data,
  });
  const resolve = useMutation({
    mutationFn: (resolution: string) => api.resolve(id, token, resolution),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alert", id] }),
  });
  const reviewContent = useMutation({
    mutationFn: () =>
      api.reviewContent(id, token, {
        score: reviewScore,
        category: reviewCategory,
        reviewer_note: reviewerNote,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alert", id] }),
  });
  if (alert.error) return <ErrorBox error={alert.error} />;
  if (!alert.data)
    return (
      <main>
        <p>Loading…</p>
      </main>
    );
  const a = alert.data;
  const currentContentSource = a.content_review_evidence?.current?.source;
  const experimentalSignal =
    a.content_review_evidence?.experimental_local_model;
  const contentLabel =
    currentContentSource === "human_review"
      ? "Human content review"
      : currentContentSource === "organizer_annotation"
        ? "Organizer content review"
        : currentContentSource === "experimental_local_model"
          ? "Experimental content signal"
          : "Content review";
  const doExport = async () => {
    const blob = await api.export(id, token);
    const href = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = href;
    link.download = `raidshield-${id}.zip`;
    link.click();
    URL.revokeObjectURL(href);
  };
  return (
    <main>
      <button className="back link-button" onClick={() => navigate(-1)}>
        ← Back
      </button>
      <div className="hero compact">
        <div>
          <p className="eyebrow">Alert detail</p>
          <h1>
            Possible coordinated {a.priority === "high" ? "harmful " : ""}
            activity
          </h1>
          <p>
            This is a prioritization signal, not proof of intent or a policy
            violation.
          </p>
        </div>
        <span className={`pill ${a.priority}`}>{a.priority} priority</span>
      </div>
      <SafetyNotice />
      <CoordinationGraph postId={a.post_id} />
      <div className="detail-grid">
        <section className="panel">
          <h2>Separate review signals</h2>
          <Score label="Coordination indicators" value={a.coordination_score} />
          <p className="hint">
            Timing, duplication, novelty, and reply concentration.
          </p>
          <Score label={contentLabel} value={a.content_review_score} />
          <p className="hint">
            Independent of the coordination calculation. Model output is a
            triage score, not a probability or determination.
          </p>
        </section>
        <section className="panel">
          <h2>Review status</h2>
          <dl>
            <div>
              <dt>Status</dt>
              <dd>{a.status.replace("_", " ")}</dd>
            </div>
            <div>
              <dt>Data confidence</dt>
              <dd>{a.confidence}</dd>
            </div>
            <div>
              <dt>Window</dt>
              <dd>
                {new Date(a.window_start).toLocaleTimeString()}–
                {new Date(a.window_end).toLocaleTimeString()}
              </dd>
            </div>
          </dl>
        </section>
      </div>
      {experimentalSignal && (
        <section className="panel model-signal">
          <p className="eyebrow">Experimental local model</p>
          <h2>Potential content-review need</h2>
          <p>
            This model can miss context or produce false alerts. It does not
            identify hate, intent, a protected target, or a policy violation.
          </p>
          {typeof experimentalSignal.score === "number" && (
            <Score
              label={
                experimentalSignal.category?.replaceAll("_", " ") ??
                "Review signal"
              }
              value={experimentalSignal.score}
            />
          )}
          {experimentalSignal.label_scores && (
            <dl className="signal-breakdown">
              {Object.entries(experimentalSignal.label_scores).map(
                ([label, score]) => (
                  <div key={label}>
                    <dt>{label.replaceAll("_", " ")}</dt>
                    <dd>{Math.round(score * 100)}%</dd>
                  </div>
                ),
              )}
              {typeof experimentalSignal.context_score === "number" && (
                <div>
                  <dt>Context uncertainty</dt>
                  <dd>{Math.round(experimentalSignal.context_score * 100)}%</dd>
                </div>
              )}
            </dl>
          )}
          <p className="hint">
            Model: {experimentalSignal.model_id ?? "local model"} · pinned
            revision{" "}
            {experimentalSignal.model_revision?.slice(0, 10) ?? "unknown"}
          </p>
        </section>
      )}
      <section className="panel">
        <h2>Why this was surfaced</h2>
        <ul className="reasons">
          {a.explanations.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
        <div className="features">
          {Object.entries(a.features)
            .filter(([, value]) => value === null || value <= 1)
            .map(([key, value]) => (
              <Score key={key} label={key.replaceAll("_", " ")} value={value} />
            ))}
        </div>
      </section>
      <section className="section-head">
        <h2>Reply-thread evidence</h2>
      </section>
      <ThreadList
        threads={threads.data?.threads ?? []}
        unknown={threads.data?.unknown_parent_replies}
      />
      <section className="panel content-review-form">
        <div>
          <p className="eyebrow">Independent human assessment</p>
          <h2>Review observed content</h2>
          <p>
            Consider context, quotation, counterspeech, criticism, and who or
            what is being addressed. This assessment does not change the
            coordination score.
          </p>
        </div>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            reviewContent.mutate();
          }}
        >
          <label>
            Review category
            <select
              value={reviewCategory}
              onChange={(event) => setReviewCategory(event.target.value)}
            >
              <option value="context_needed">Context needed</option>
              <option value="needs_review">Needs review</option>
              <option value="safety_concern">Safety concern</option>
              <option value="no_concern">No concern</option>
            </select>
          </label>
          <label>
            Review score: {Math.round(reviewScore * 100)}%
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={reviewScore}
              onChange={(event) => setReviewScore(Number(event.target.value))}
            />
          </label>
          <label>
            Reviewer note
            <input
              value={reviewerNote}
              maxLength={2000}
              onChange={(event) => setReviewerNote(event.target.value)}
              placeholder="Record context without adding identities"
            />
          </label>
          <button disabled={!token || reviewContent.isPending}>
            {reviewContent.isPending ? "Saving…" : "Save human content review"}
          </button>
          {reviewContent.isSuccess && (
            <p role="status">Human content review saved.</p>
          )}
          {reviewContent.error && <ErrorBox error={reviewContent.error} />}
          {!token && (
            <p className="hint">
              Enter the local administrator token in Test Lab before reviewing.
            </p>
          )}
        </form>
      </section>
      <section className="review panel">
        <div>
          <h2>Human resolution</h2>
          <p>Record context so future false alerts can be inspected.</p>
        </div>
        <div className="actions">
          <button
            disabled={!token || resolve.isPending}
            onClick={() => resolve.mutate("benign_coordination")}
          >
            Mark benign coordination
          </button>
          <button
            disabled={!token || resolve.isPending}
            onClick={() => resolve.mutate("confirmed_coordination")}
          >
            Confirm observed coordination
          </button>
          <button className="secondary" disabled={!token} onClick={doExport}>
            Export redacted evidence
          </button>
        </div>
        {!token && (
          <p className="hint">
            Enter the local administrator token in Test Lab to review or export.
          </p>
        )}
      </section>
    </main>
  );
}

function TestLab({
  token,
  setToken,
}: {
  token: string;
  setToken: (x: string) => void;
}) {
  const fixtures = useQuery({ queryKey: ["fixtures"], queryFn: api.fixtures });
  const qc = useQueryClient();
  const [selected, setSelected] = useState("reply_thread_burst");
  const [offlineFile, setOfflineFile] = useState<File | null>(null);
  const [resetOffline, setResetOffline] = useState(false);
  const replay = useMutation({
    mutationFn: () => api.replay(selected, token, true),
    onSuccess: () => {
      qc.invalidateQueries();
    },
  });
  const offlineImport = useMutation({
    mutationFn: () => api.importOffline(offlineFile!, token, resetOffline),
    onSuccess: () => qc.invalidateQueries(),
  });
  const active = fixtures.data?.find((f) => f.fixture_name === selected);
  return (
    <main>
      <div className="hero">
        <div>
          <p className="eyebrow">Safe demonstration</p>
          <h1>Test Lab</h1>
          <p>
            Import an authorized local JSON dataset or replay bundled synthetic
            events through the same normalized pipeline.
          </p>
        </div>
      </div>
      <SafetyNotice />
      <div className="lab">
        <section className="panel">
          <label>
            Local administrator token
            <input
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              autoComplete="off"
              placeholder="From ADMIN_TOKEN"
            />
          </label>
          <label>
            Safe fixture
            <select
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
            >
              {fixtures.data?.map((f) => (
                <option key={f.fixture_name} value={f.fixture_name}>
                  {f.fixture_name.replaceAll("_", " ")}
                </option>
              ))}
            </select>
          </label>
          {active && (
            <div className="fixture-note">
              <strong>{active.description}</strong>
              <p>Origin: {active.content_origin}</p>
              <p>
                Expected:{" "}
                {active.expected_outcome.coordination_alert
                  ? "coordination alert"
                  : "no coordination alert"}
                {active.expected_outcome.high_priority
                  ? " · high priority"
                  : ""}
              </p>
            </div>
          )}
          <button
            disabled={!token || replay.isPending}
            onClick={() => replay.mutate()}
          >
            {replay.isPending ? "Processing…" : "Reset and replay immediately"}
          </button>
          {replay.error && <ErrorBox error={replay.error} />}
        </section>
        <section className="panel">
          <p className="eyebrow">Offline data</p>
          <h2>Import local JSON</h2>
          <p>
            The file is sent only to the localhost backend, validated in memory,
            and never retained as an upload. Source identifiers are immediately
            installation-hashed.
          </p>
          <label>
            Offline JSON dataset
            <input
              type="file"
              accept="application/json,.json"
              onChange={(event) =>
                setOfflineFile(event.target.files?.[0] ?? null)
              }
            />
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={resetOffline}
              onChange={(event) => setResetOffline(event.target.checked)}
            />{" "}
            Delete existing local review data before import
          </label>
          <button
            disabled={!token || !offlineFile || offlineImport.isPending}
            onClick={() => offlineImport.mutate()}
          >
            {offlineImport.isPending ? "Importing…" : "Import offline dataset"}
          </button>
          {offlineImport.error && <ErrorBox error={offlineImport.error} />}
        </section>
        {replay.data && (
          <section className="panel result" aria-live="polite">
            <span className="pill">{replay.data.status}</span>
            <h2>
              {replay.data.processed_events} of {replay.data.total_events}{" "}
              events processed
            </h2>
            <p>
              The fixture used keyed pseudonyms and retained no raw participant
              identifiers.
            </p>
            <div className="actions">
              {replay.data.result_alert_id && (
                <Link
                  className="button"
                  to={`/alerts/${replay.data.result_alert_id}`}
                >
                  Open generated alert
                </Link>
              )}
              {replay.data.result_post_id && (
                <Link
                  className="button secondary"
                  to={`/posts/${replay.data.result_post_id}`}
                >
                  Open post
                </Link>
              )}
            </div>
          </section>
        )}
        {offlineImport.data && (
          <section className="panel result" aria-live="polite">
            <span className="pill">offline import complete</span>
            <h2>
              {offlineImport.data.created_events} of{" "}
              {offlineImport.data.total_events} events imported
            </h2>
            <p>
              {offlineImport.data.duplicate_events} duplicates skipped. The
              original file and raw participant identifiers were not retained.
            </p>
            <div className="actions">
              {offlineImport.data.result_alert_ids[0] && (
                <Link
                  className="button"
                  to={`/alerts/${offlineImport.data.result_alert_ids[0]}`}
                >
                  Open imported alert
                </Link>
              )}
              {offlineImport.data.result_post_ids[0] && (
                <Link
                  className="button secondary"
                  to={`/posts/${offlineImport.data.result_post_ids[0]}`}
                >
                  Open imported surface
                </Link>
              )}
            </div>
          </section>
        )}
      </div>
    </main>
  );
}

const defaults = {
  alert_threshold: 0.7,
  minimum_unique_authors: 4,
  similarity_threshold: 0.85,
  cold_start_threshold: 6,
  raw_text_retention_hours: 24,
  aggregate_retention_days: 30,
  store_raw_text: false,
};
function SettingsPage({ token }: { token: string }) {
  const current = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const [form, setForm] = useState(defaults);
  const save = useMutation({ mutationFn: () => api.saveSettings(form, token) });
  const shown = current.data ? { ...defaults, ...current.data } : form;
  return (
    <main>
      <div className="hero compact">
        <div>
          <p className="eyebrow">Local configuration</p>
          <h1>Detection settings</h1>
        </div>
      </div>
      <SafetyNotice />
      <form
        className="panel settings"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        {Object.entries(shown)
          .filter(([k]) => k !== "store_raw_text")
          .map(([key, value]) => (
            <label key={key}>
              {key.replaceAll("_", " ")}
              <input
                type="number"
                step={key.includes("threshold") ? 0.01 : 1}
                min={key.includes("threshold") ? 0.1 : 1}
                max={key.includes("threshold") ? 1 : 365}
                defaultValue={Number(value)}
                onChange={(e) =>
                  setForm((prev) => ({
                    ...prev,
                    [key]: Number(e.target.value),
                  }))
                }
              />
            </label>
          ))}
        <label className="check">
          <input
            type="checkbox"
            checked={form.store_raw_text}
            onChange={(e) =>
              setForm((prev) => ({ ...prev, store_raw_text: e.target.checked }))
            }
          />{" "}
          Store encrypted raw text (requires a configured key)
        </label>
        <div className="actions">
          <button disabled={!token || save.isPending}>
            Save validated settings
          </button>
          <button
            type="button"
            className="secondary"
            onClick={() => setForm(defaults)}
          >
            Restore defaults
          </button>
        </div>
        {!token && (
          <p className="hint">
            Enter the session token in Test Lab before changing settings.
          </p>
        )}
        {save.error && <ErrorBox error={save.error} />}
      </form>
    </main>
  );
}
function SafetyPage({ token }: { token: string }) {
  const [confirm, setConfirm] = useState("");
  const remove = useMutation({ mutationFn: () => api.deleteData(token) });
  return (
    <main>
      <div className="hero">
        <div>
          <p className="eyebrow">Boundaries by design</p>
          <h1>Safety & privacy</h1>
          <p>
            RaidShield analyzes only offline datasets that an operator is
            authorized to process.
          </p>
        </div>
      </div>
      <SafetyNotice />
      <div className="prose">
        <section>
          <h2>What it observes</h2>
          <p>
            Timing, near-duplicate text patterns, first-seen participation,
            reply concentration, and pseudonymous overlap inside the imported
            comment dataset.
          </p>
        </section>
        <section>
          <h2>What it cannot know</h2>
          <p>
            It cannot see or verify anything outside the imported file, know a
            person’s intent, infer protected traits, or build individual risk
            scores.
          </p>
        </section>
        <section>
          <h2>Data controls</h2>
          <p>
            Raw identifiers are immediately replaced with installation-keyed
            HMAC digests. Raw text is hidden by default; if enabled, it is
            encrypted locally and expires after 24 hours by default. Aggregate
            pseudonymous records expire after 30 days.
          </p>
        </section>
        <section>
          <h2>Experimental content screening</h2>
          <p>
            If explicitly enabled, an optional local multilingual model can
            surface potential insults, targeted hostility, or threats for human
            review. Its score remains separate from coordination and does not
            determine hate, intent, identity, or a policy violation.
          </p>
        </section>
        <section>
          <h2>Safe fixtures</h2>
          <p>
            Bundled demonstrations contain synthetic neutral placeholders or
            explicit organizer redactions. They contain no hateful or
            identifying content.
          </p>
        </section>
        <section className="danger-zone">
          <h2>Delete local data</h2>
          <p>
            This removes posts, events, reviews, and alerts while leaving
            fixtures and configuration intact.
          </p>
          <label>
            Type <code>DELETE LOCAL RAIDSHIELD DATA</code>
            <input
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
            />
          </label>
          <button
            disabled={!token || confirm !== "DELETE LOCAL RAIDSHIELD DATA"}
            onClick={() => remove.mutate()}
          >
            Delete local data
          </button>
          {remove.data && <p role="status">Local application data deleted.</p>}
        </section>
      </div>
    </main>
  );
}

export default function App() {
  const [token, setToken] = useState("");
  return (
    <div className="app">
      <ScrollToTop />
      <header>
        <Link className="brand" to="/">
          <span>RS</span>
          <div>
            RaidShield<small>Moderator decision support</small>
          </div>
        </Link>
        <nav aria-label="Primary">
          <NavLink to="/">Overview</NavLink>
          <NavLink to="/test-lab">Test Lab</NavLink>
          <NavLink to="/settings">Settings</NavLink>
          <NavLink to="/safety">Safety</NavLink>
        </nav>
      </header>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/posts/:id" element={<PostPage token={token} />} />
        <Route path="/alerts/:id" element={<AlertPage token={token} />} />
        <Route
          path="/test-lab"
          element={<TestLab token={token} setToken={setToken} />}
        />
        <Route path="/settings" element={<SettingsPage token={token} />} />
        <Route path="/safety" element={<SafetyPage token={token} />} />
      </Routes>
      <footer className="site-footer">
        <span>RaidShield MVP · Local-first</span>
        <span>Observable indicators · Human judgment</span>
      </footer>
    </div>
  );
}
