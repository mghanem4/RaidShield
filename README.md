# RaidShield

RaidShield is an offline, local-first moderator decision-support MVP for comment datasets. It reconstructs reply threads and surfaces explainable indicators—timing bursts, near-duplicate text, experimental semantic-context similarity, participant novelty, synchronization, and thread concentration—so a human can review changing activity and preserve a redacted evidence package. An interactive coordination graph makes repeated or contextually similar activity, close timing, and shared reply targets visible between pseudonymous participants.

An optional experimental multilingual zero-shot model can independently surface potential content-review needs. It is disabled by default, runs locally, does not alter the coordination score, and never determines hate, intent, identity, or a policy violation.

Every reply is also compared transiently with its direct parent and sibling replies. Structural context—reply position, timing from the parent, and exact/near sibling repetition—is available even when the model is disabled. When enabled, the same pinned local safetensors model adds an experimental relationship ranking such as support, opposition, restatement, clarification, unrelated, or ambiguous. These labels require human interpretation and never alter coordination or content-review scores.

> **Safety statement:** RaidShield detects observable coordination indicators in authorized offline data. It does not determine intent, infer protected characteristics, identify hate, establish a policy violation, or see data that was not imported. Every alert requires human review; no moderation action is automated.

## Screenshot

Run the replay demo locally to inspect the responsive dashboard, Test Lab, post/thread detail, alert explanation, settings, safety, and export flows. A repository screenshot is intentionally not committed because it can become stale; the clean fixture path below recreates the view deterministically.

## Architecture

Validated offline JSON datasets and bundled replay fixtures pass through isolated adapters into one normalized ingestion service. Raw participant identifiers are immediately transformed with keyed HMAC-SHA-256. SQLAlchemy/Alembic persist pseudonymous events in SQLite, pure deterministic functions calculate feature snapshots, FastAPI serves review/export APIs, and React renders the local moderator UI. See [offline data format](docs/OFFLINE_DATA.md), [architecture](docs/ARCHITECTURE.md), [data dictionary](docs/DATA_DICTIONARY.md), and [threat model](docs/THREAT_MODEL.md).

The post and alert pages include a derived participant graph. Nodes are short pseudonymous labels. Without semantic analysis, edges retain the deterministic exact-text/timing/shared-target weights. When semantic context was evaluated, edges combine exact text (25%), semantic-context ranking (30%), activity within 30 seconds (30%), and shared reply targets (15%). Semantic similarity alone is not accepted without corroborating timing, exact-text, or thread evidence. Connected components are shown as clusters. Browser-only layout changes never alter scores or stored data. This is behavioral evidence, not a bot classifier or proof of coordination.

## Prerequisites

- Python 3.12 or newer is recommended and is the container target. The code is also CI-compatible with Python 3.10–3.11 for local validation.
- Node.js 20 or newer
- OpenSSL
- Optional: Docker Compose

## Local setup

```bash
make setup
cp .env.example .env
make keys
```

Copy the two generated values into `.env`, generate a separate high-entropy `ADMIN_TOKEN`, keep `STORE_RAW_TEXT=false`, then migrate:

```bash
make migrate
```

Start two terminals:

```bash
make backend
make frontend
```

Open <http://127.0.0.1:5173>. The API documentation is at <http://127.0.0.1:8000/docs>. Both development servers bind to localhost.

For containers, create `.env` first and run `docker compose up --build`. Ports remain published only on `127.0.0.1`.

## Replay demonstration

Use **Test Lab**, enter the `ADMIN_TOKEN` stored in your local `.env`, select `reply_thread_burst`, and choose immediate replay. The token is held only in React memory and is lost on refresh. Or run:

```bash
export ADMIN_TOKEN='the same local value configured in .env'
make demo
```

Fixtures are bundled synthetic placeholders or organizer redactions. Arbitrary fixture paths and uploads are not accepted. See [demo script](docs/DEMO_SCRIPT.md).

## Offline JSON import

Open **Test Lab**, enter the local `ADMIN_TOKEN`, select a `.json` dataset, and import it. The file is validated in memory, is not retained, and is processed through the same ingestion service as replay. A safe example is provided at [`examples/offline_safe_batch.json`](examples/offline_safe_batch.json). The complete schema and privacy contract are in [OFFLINE_DATA.md](docs/OFFLINE_DATA.md).

## Optional local content detector

The optional detector is a triage aid, not a hate classifier. Install and cache its pinned model once while online:

```bash
make content-model
```

The model weights are approximately 1.1 GB and runtime memory will be higher. After caching, enable it in `.env` and restart the backend:

```env
CONTENT_DETECTOR_ENABLED=true
CONTENT_DETECTOR_LOCAL_FILES_ONLY=true
CONTENT_DETECTOR_DEVICE=auto
```

Confirm offline runtime readiness with neutral safe samples:

```bash
make content-smoke
```

With `auto`, PyTorch selects Apple MPS when available and otherwise uses CPU. At runtime, `local_files_only=true` prevents model downloads. Model loading requires safetensors and will not fall back to pickle-based weight files. Imported text is analyzed transiently before it is discarded or encrypted. Bundled replay fixtures are not model-evaluated unless an organizer explicitly marks an event `content_detector_eligible`; this preserves safe fixture semantics.

For eligible replies, model-enabled ingestion performs both independent content triage and parent–reply context ranking. The ranking score is not a calibrated probability. Parent and reply plaintext are not stored in context metadata.

Post and alert thread views expose a per-comment **Model review evidence** panel when evaluation metadata exists. It shows the complete abstract-label ranking, configured threshold, parent context when available under the existing text-access controls, sibling-repetition counts, and a deterministic calculation summary. The summary describes which score crossed which threshold; it does not claim to reveal the model's internal reasoning. Evaluated comments below threshold remain distinguishable from comments flagged for human review.

The configured `0.65` threshold is an uncalibrated starting point, not a probability. Do not present the feature as validated for English, Arabic, Arabizi, code-switching, insults, or anti-Muslim hostility until an organizer-approved evaluation reports per-language precision, recall, false positives, and uncertainty.

## Optional semantic-context coordination

The semantic analyzer uses a separate pinned multilingual sentence-embedding model. It embeds `parent + reply` transiently, compares different participants with matching reply roles inside a 60-second window, and persists only hashed event references plus abstract similarities and timing/thread facts. Plaintext and embedding vectors are never persisted.

```bash
make semantic-model
make semantic-smoke
```

Then enable it and restart the backend:

```env
SEMANTIC_CONTEXT_ENABLED=true
SEMANTIC_CONTEXT_LOCAL_FILES_ONLY=true
SEMANTIC_CONTEXT_DEVICE=auto
```

The default `0.78` threshold is an uncalibrated starting point. The model can conflate common reactions, quotation, counterspeech, or sarcasm. It requires corroborating behavioral evidence and human review, and does not establish coordination, automation, intent, agreement, or hate.

## Validation

```bash
make lint
make format-check
make typecheck
make test
make build
cd frontend && npx playwright install chromium && cd ..
make e2e
```

The backend suite includes unit, integration, offline import, fixture outcome, retention, encryption, idempotency, review, experimental-detector isolation, sanitized failure, and ZIP-manifest checks. The frontend suite covers empty/activity states, separate score display, transparent experimental signals, and replies. Playwright covers offline browser import plus the full replay, alert, resolution, and export flow.

## Environment variables

| Variable | Purpose | Required |
|---|---|---|
| `APP_ENV` | `development`, `test`, or deployment environment | Yes |
| `ADMIN_TOKEN` | Local mutation bearer token | Yes outside tests; use high entropy |
| `DATABASE_URL` | SQLAlchemy URL | Defaults to local SQLite |
| `PSEUDONYMIZATION_KEY` | Installation-specific HMAC key | Yes |
| `DATA_ENCRYPTION_KEY` | Fernet key for optional text persistence | When `STORE_RAW_TEXT=true` |
| `STORE_RAW_TEXT` | Persist locally encrypted comment text | Defaults to `false` |
| `RAW_TEXT_RETENTION_HOURS` | Ciphertext retention | Default 24 |
| `AGGREGATE_RETENTION_DAYS` | Pseudonymous record retention | Default 30 |
| `CONTENT_DETECTOR_ENABLED` | Enable optional local experimental triage | Defaults to `false` |
| `CONTENT_DETECTOR_MODEL` | Hugging Face model identifier | Pinned default model |
| `CONTENT_DETECTOR_REVISION` | Immutable model revision | Required when enabled |
| `CONTENT_DETECTOR_THRESHOLD` | Uncalibrated review threshold | Default `0.65` |
| `CONTENT_DETECTOR_DEVICE` | `auto`, `cpu`, or `mps` | Default `auto` |
| `CONTENT_DETECTOR_LOCAL_FILES_ONLY` | Prevent runtime downloads | Default `true` |
| `SEMANTIC_CONTEXT_ENABLED` | Enable experimental semantic coordination | Defaults to `false` |
| `SEMANTIC_CONTEXT_MODEL` | Multilingual embedding model identifier | Pinned default model |
| `SEMANTIC_CONTEXT_REVISION` | Immutable embedding-model revision | Required when enabled |
| `SEMANTIC_CONTEXT_THRESHOLD` | Uncalibrated semantic ranking threshold | Default `0.78` |
| `SEMANTIC_CONTEXT_TIME_WINDOW_SECONDS` | Maximum comparison timing gap | Default `60` |
| `SEMANTIC_CONTEXT_DEVICE` | `auto`, `cpu`, or `mps` | Default `auto` |
| `SEMANTIC_CONTEXT_LOCAL_FILES_ONLY` | Prevent runtime downloads | Default `true` |
| `FRONTEND_ORIGIN` | Allowed local browser origin | Default `http://localhost:5173` |

Never paste secrets into chat, commit `.env`, or expose them in screenshots/logs.

## Retention and deletion

Ciphertext is cleared after 24 hours and pseudonymous records after 30 days by default. Run the authenticated `POST /api/v1/admin/purge-expired` from a local scheduled command if desired. The Safety page offers explicit-confirmation deletion of all local application data while preserving fixtures/configuration. Database files and `.env` are ignored by Git.

## Known limitations

This is a local offline MVP with SQLite, one in-memory session token, and in-process replay tasks. It performs no platform collection, OAuth onboarding, multi-tenancy, profile enrichment, automated moderation, or cross-dataset identity tracking. See [LIMITATIONS.md](docs/LIMITATIONS.md) for detection and scale caveats.

## Development and data disclosure

OpenAI Codex assisted with implementation, testing, and documentation under the repository specification. RaidShield does not call an external AI or LLM service at runtime. Feature calculations are local and deterministic. Test data contains only synthetic safe placeholders and explicit organizer-redaction tokens; it contains no scraped or hateful content.

## License

MIT. See [LICENSE](LICENSE).
