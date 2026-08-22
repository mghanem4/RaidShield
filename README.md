# RaidShield

RaidShield is a local-first moderator decision-support MVP for comments and replies on an authorized Instagram professional account. It reconstructs reply threads and surfaces deterministic, explainable indicators—timing bursts, near-duplicate text, participant novelty, synchronization, and thread concentration—so a human can review changing activity and preserve a redacted evidence package.

> **Safety statement:** RaidShield detects observable coordination indicators inside an authorized comment surface. It does not determine intent, infer protected characteristics, identify hate, establish a policy violation, or see private messages. Every alert requires human review; no moderation action is automated.

## Screenshot

Run the replay demo locally to inspect the responsive dashboard, Test Lab, post/thread detail, alert explanation, settings, safety, and export flows. A repository screenshot is intentionally not committed because it can become stale; the clean fixture path below recreates the view deterministically.

## Architecture

Replay fixtures and signed Instagram webhook payloads pass through isolated adapters into one normalized ingestion service. Raw author identifiers are immediately transformed with keyed HMAC-SHA-256. SQLAlchemy/Alembic persist pseudonymous events in SQLite, pure deterministic functions calculate feature snapshots, FastAPI serves review/export APIs, and React renders the local moderator UI. See [architecture](docs/ARCHITECTURE.md), [data dictionary](docs/DATA_DICTIONARY.md), and [threat model](docs/THREAT_MODEL.md).

## Prerequisites

- Python 3.12 or newer is recommended and is the container target. The code is also CI-compatible with Python 3.10–3.11 for local validation.
- Node.js 20 or newer
- OpenSSL
- Optional: Docker Compose

## Local setup (no Meta credentials)

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

The backend suite includes unit, integration, signed webhook, fixture outcome, retention, encryption, idempotency, review, and ZIP-manifest checks. The frontend suite covers empty/activity states, separate score display, and replies. Playwright covers the full reply-burst replay, alert, resolution, and export flow.

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
| `META_VERIFY_TOKEN` | Owner-selected webhook verification token | Live webhook only |
| `META_APP_SECRET` | Signature-validation secret | Live webhook only |
| `META_ACCESS_TOKEN` | Future authorized Graph reads | Optional/not used by replay |
| `META_IG_USER_ID` | Authorized professional account identifier | Optional/not used by replay |
| `META_GRAPH_VERSION` | Explicit Graph API version | Set after checking Meta docs |
| `FRONTEND_ORIGIN` | Allowed local browser origin | Default `http://localhost:5173` |

Never paste secrets into chat, commit `.env`, or expose them in screenshots/logs.

## Meta integration

`GET /webhooks/instagram` performs constant-time verification-token comparison. `POST /webhooks/instagram` verifies `X-Hub-Signature-256` over the unparsed raw body, rejects invalid or oversized input, normalizes supported comment/reply events, and uses the same ingestion service as replay. Current owner dashboard steps and access caveats are in [META_SETUP.md](docs/META_SETUP.md).

Live webhook delivery has **not** been tested in this repository; it is implemented and tested with signed synthetic payloads only. Do not claim live support until an owner-authorized test succeeds.

## Retention and deletion

Ciphertext is cleared after 24 hours and pseudonymous records after 30 days by default. Run the authenticated `POST /api/v1/admin/purge-expired` from a local scheduled command if desired. The Safety page offers explicit-confirmation deletion of all local application data while preserving fixtures/configuration. Database files and `.env` are ignored by Git.

## Known limitations

This is a single-account local MVP with SQLite, one in-memory session token, and in-process background tasks. It performs no OAuth onboarding, multi-tenancy, profile enrichment, automated moderation, private-message access, or cross-community tracking. See [LIMITATIONS.md](docs/LIMITATIONS.md) for detection, scale, and integration caveats.

## Development and data disclosure

OpenAI Codex assisted with implementation, testing, and documentation under the repository specification. RaidShield does not call an external AI or LLM service at runtime. Feature calculations are local and deterministic. Test data contains only synthetic safe placeholders and explicit organizer-redaction tokens; it contains no scraped or hateful content.

## License

MIT. See [LICENSE](LICENSE).
