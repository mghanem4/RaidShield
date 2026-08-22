# RaidShield MVP Status

Last updated: 2026-08-22

## Completed

- **Milestone 0:** Read the full 1,428-line specification; inspected the initially empty repository; recorded plan and decisions.
- **Milestone 1:** FastAPI/React scaffold, validated configuration, Alembic startup, health API, localhost commands, Docker Compose, and dashboard shell.
- **Milestone 2:** Normalized events, migration-backed SQLite schema/indexes, immediate HMAC pseudonymization, optional Fernet encryption, five safe fixtures, idempotent replay, posts, timelines, and reply-thread queries.
- **Milestone 3:** Deterministic burst, character TF-IDF similarity, synchronization, novelty, and concentration; weighted score; data-confidence labels; explanations; minimum-author gate; alert merging/audits; fixture outcome matrix.
- **Milestone 4:** Responsive dashboard, post and alert details, feature bars, pseudonymous reply view, Test Lab, settings, safety page, and human resolution. Direct UI inspection fixed route scroll restoration and removed remote fonts.
- **Milestone 5:** Separate content review, deterministic redacted HTML/JSON ZIP export, SHA-256 manifest, retention purge, and confirmed local-data deletion.
- **Milestone 6:** Webhook verification, raw-body HMAC validation, size limit, comment/reply normalization, sanitized errors, background ingestion, and signed safe samples.
- **Milestone 7:** Complete docs; tests, coverage, lint, formatting, Python/TypeScript types, build, migration/startup, E2E, export integrity, UI inspection, and dependency audit.

## Validation results

- Backend: 20 passed; 94.15% core coverage (target 80%).
- Frontend: 3 component tests passed.
- E2E: 1 Playwright replay/review/export flow passed.
- Ruff, ESLint, Ruff format, Prettier, mypy, and TypeScript passed.
- Vite production build passed (71 modules; approximately 233 kB JS / 74 kB gzip).
- Full `npm audit`: 0 vulnerabilities after upgrading React Router, Vite, and Vitest.
- Alembic migration and backend startup ran in final E2E validation.
- Evidence file set, identity-field omission, and every manifest hash passed integration validation.

## Blocked by owner-controlled requirements

- Live Instagram delivery has **not** been tested. It requires Meta credentials, public HTTPS, a professional test account/media, dashboard subscription, and any current access approval. See `docs/META_SETUP.md`.

## Deferred production work

- OAuth/multi-tenancy, App Review submission, RBAC, PostgreSQL, durable queues, rate limiting, cursor pagination, tenant isolation, managed keys, notifications, formal evaluation, security assessment, and public deployment.
- Adjacent-window persistence for `high` data confidence and optional cross-post overlap.
