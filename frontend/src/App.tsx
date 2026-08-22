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
import type { Alert, ThreadEvent } from "./types";

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
          <p className="eyebrow">Protected comment surface</p>
          <h1>Activity overview</h1>
          <p>
            Explainable group-level indicators for a moderator-owned account.
          </p>
        </div>
        <div className="mode">
          <i className={health.data?.database_ready ? "online" : ""} />
          <span>{health.data?.mode ?? "checking"} mode</span>
          <small>
            {health.data?.meta_configured
              ? "Webhook configured"
              : "Replay ready · Meta not configured"}
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
          <span>Protected posts</span>
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
          <p className="eyebrow">Recent surfaces</p>
          <h2>Monitored posts</h2>
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
function PostPage() {
  const { id = "" } = useParams();
  const post = useQuery({
    queryKey: ["post", id],
    queryFn: () => api.post(id),
  });
  const threads = useQuery({
    queryKey: ["threads", id],
    queryFn: () => api.threads(id),
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
              </div>
            ))}
          </div>
        </article>
      ))}
      {unknown.length > 0 && (
        <article className="thread">
          <h3>Unknown or unavailable parent</h3>
          {unknown.map((x) => (
            <p key={x.id}>
              {x.participant} · {x.content}
            </p>
          ))}
        </article>
      )}
    </div>
  );
}

function AlertPage({ token }: { token: string }) {
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const alert = useQuery({
    queryKey: ["alert", id],
    queryFn: () => api.alert(id),
  });
  const threads = useQuery({
    queryKey: ["alertThreads", alert.data?.post_id],
    queryFn: () => api.threads(alert.data!.post_id),
    enabled: !!alert.data,
  });
  const resolve = useMutation({
    mutationFn: (resolution: string) => api.resolve(id, token, resolution),
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
      <div className="detail-grid">
        <section className="panel">
          <h2>Separate review signals</h2>
          <Score label="Coordination indicators" value={a.coordination_score} />
          <p className="hint">
            Timing, duplication, novelty, and reply concentration.
          </p>
          <Score
            label="Human / organizer content review"
            value={a.content_review_score}
          />
          <p className="hint">Independent of the coordination calculation.</p>
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
      <section className="panel">
        <h2>Why this was surfaced</h2>
        <ul className="reasons">
          {a.explanations.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
        <div className="features">
          {Object.entries(a.features)
            .filter(([, v]) => v <= 1)
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
  const replay = useMutation({
    mutationFn: () => api.replay(selected, token, true),
    onSuccess: () => {
      qc.invalidateQueries();
    },
  });
  const active = fixtures.data?.find((f) => f.fixture_name === selected);
  return (
    <main>
      <div className="hero">
        <div>
          <p className="eyebrow">Safe demonstration</p>
          <h1>Test Lab</h1>
          <p>
            Replay bundled synthetic events through the same normalized pipeline
            used by webhooks.
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
        {replay.data && (
          <section className="panel result" aria-live="polite">
            <span className="pill">{replay.data.status}</span>
            <h2>
              {replay.data.processed_events} of {replay.data.total_events}{" "}
              events processed
            </h2>
            <p>
              The fixture used keyed pseudonyms and retained no raw usernames.
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
            RaidShield observes activity patterns only on an account that
            voluntarily authorized monitoring.
          </p>
        </div>
      </div>
      <SafetyNotice />
      <div className="prose">
        <section>
          <h2>What it observes</h2>
          <p>
            Timing, near-duplicate text patterns, first-seen participation,
            reply concentration, and pseudonymous overlap inside the protected
            comment surface.
          </p>
        </section>
        <section>
          <h2>What it cannot know</h2>
          <p>
            It cannot see direct messages, private activity, off-platform
            planning, or a person’s intent. It does not infer protected traits
            or build individual risk scores.
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
        <Route path="/posts/:id" element={<PostPage />} />
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
