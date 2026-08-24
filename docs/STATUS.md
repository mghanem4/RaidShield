# RaidShield MVP Status

Last updated: 2026-08-24

## Completed

- **Milestone 0:** Read the full 1,428-line specification; inspected the initially empty repository; recorded plan and decisions.
- **Milestone 1:** FastAPI/React scaffold, validated configuration, Alembic startup, health API, localhost commands, Docker Compose, and dashboard shell.
- **Milestone 2:** Normalized events, migration-backed SQLite schema/indexes, immediate HMAC pseudonymization, optional Fernet encryption, five safe fixtures, idempotent replay, posts, timelines, and reply-thread queries.
- **Milestone 3:** Deterministic burst, character TF-IDF similarity, synchronization, novelty, and concentration; weighted score; data-confidence labels; explanations; minimum-author gate; alert merging/audits; fixture outcome matrix.
- **Milestone 4:** Responsive dashboard, post and alert details, feature bars, pseudonymous reply view, Test Lab, settings, safety page, and human resolution. Direct UI inspection fixed route scroll restoration and removed remote fonts.
- **Milestone 5:** Separate content review, deterministic redacted HTML/JSON ZIP export, SHA-256 manifest, retention purge, and confirmed local-data deletion.
- Authenticated thread views and exports show locally decrypted content only when raw-text storage was enabled before ingestion.
- Optional local multilingual content triage is implemented behind a disabled-by-default flag, with pinned provenance, safetensors-only loading, safe abstract labels, model-failure isolation, human override, and transparent UI/export disclosure.
- **Offline pivot:** Removed all live-source routes, adapters, credentials, proxy rules, and tests. Added authenticated, strict, bounded offline JSON import with in-memory validation, dataset-scoped source-ID hashing, immediate participant pseudonymization, shared normalized ingestion, UI upload flow, safe example data, and browser coverage.
- **Coordination graph:** Added deterministic weighted participant edges, connected-component clusters, privacy-minimized graph API, interactive keyboard-accessible SVG, draggable/pinnable nodes, pan/zoom, force arrangement, reset controls, evidence inspector, post/alert integration, redacted export data, size caps, and harmless organic/coordinated tests.
- **Reply context:** Added shared offline/replay parent-and-sibling enrichment, transient parent text, structural timing/order/repetition evidence, optional safetensors parent–reply relationship ranking, thread disclosures, graph summaries, redacted exports, and harmless privacy/failure tests. Context stays independent of all alert scores.
- **Per-comment model evidence:** Post and alert threads now show an allowlisted evidence panel with flagged/below-threshold status, complete rankings, threshold comparison, authorized parent/comment context, repetition measurements, provenance, and a faithful template explanation that does not claim hidden model reasoning.
- **Semantic-context coordination:** Added an optional pinned multilingual safetensors encoder for transient `parent + reply` embeddings, time/role-bounded cross-participant matching, privacy-safe pair metadata, a separate alert feature, corroboration-gated graph edges, per-comment evidence, graph explanations, and harmless tests. The local smoke pair ranked a harmless paraphrase at 0.8648 versus 0.3395 for unrelated context; this validates mechanics only.
- **Milestone 7:** Complete docs; tests, coverage, lint, formatting, Python/TypeScript types, build, migration/startup, E2E, export integrity, UI inspection, and dependency audit.

## Validation results

- Backend: 47 passed; 92.36% core coverage (target 80%).
- Frontend: 3 component tests passed.
- E2E: 1 Playwright offline-import/context/graph-drag/zoom/replay/review/export flow passed.
- Playwright uses isolated ports and credentials, so it can run while the development app is open.
- Ruff, ESLint, Ruff format, Prettier, mypy, and TypeScript passed.
- Vite production build passed (72 modules; 255.07 kB JS / 80.05 kB gzip).
- Full `npm audit`: 0 vulnerabilities after upgrading React Router, Vite, and Vitest.
- Alembic migration and backend startup ran in final E2E validation.
- Evidence file set, identity-field omission, and every manifest hash passed integration validation.
- Optional PyTorch/Transformers packages and the pinned approximately 1.1 GB model are installed and cached. Offline MPS loading succeeded on this M3; a neutral safe smoke set stayed below threshold, with roughly 5–7 seconds for first-call initialization and 0.06–0.15 seconds for warm calls. This validates runtime mechanics only. Adapter behavior is also covered with deterministic test doubles; English, Arabic, Arabizi, code-switching, calibration, fairness, and real-world latency remain evaluation requirements rather than claimed capabilities.
- The pinned approximately 471 MB multilingual semantic model is also cached as safetensors. Offline MPS loading and harmless paraphrase/unrelated separation succeeded mechanically; semantic thresholds, per-language quality, false coordination rates, and production latency remain evaluation requirements.

## Deferred production work

- Multi-tenancy, RBAC, PostgreSQL, durable queues, rate limiting, cursor pagination, tenant isolation, managed keys, notifications, formal evaluation, security assessment, and public deployment.
- Adjacent-window persistence for `high` data confidence and optional cross-post overlap.
- Organizer-approved multilingual content-detector evaluation, threshold calibration, abstention tuning, and per-language error analysis.
