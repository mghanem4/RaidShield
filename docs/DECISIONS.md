# Technical Decisions

## 2026-08-21

1. **Clean scaffold.** The repository contained only the authoritative specification, so there is no existing stack or local work to preserve.
2. **Compact modular monolith.** FastAPI, SQLAlchemy, Alembic, SQLite, React, TypeScript, and Vite follow the recommended stack. Detection stays in pure Python functions; source-specific parsing stays in adapters.
3. **Synchronous immediate replay.** Immediate replay is processed in-request for deterministic tests and direct result links. Paced replay uses a FastAPI background task. Both call the same ingestion service.
4. **No raw text when disabled.** Fingerprints and transient similarity inputs are calculated before persistence. With `STORE_RAW_TEXT=false`, no reversible text is stored. Alert feature snapshots retain aggregate cluster measurements only.
5. **Installation-scoped identities.** Full HMAC-SHA-256 digests are stored and only a short prefix is displayed. Raw source author identifiers are never added to domain objects or database rows.
6. **SQLite MVP concurrency.** The application uses short transactions and a background task only for paced replay. A production queue and PostgreSQL remain intentionally deferred.
7. **Local administrator authentication.** Mutations require a bearer token. Read APIs are intended only for services bound to localhost; this is not public-deployment authentication.
8. **Meta status.** Webhook behavior will be implemented and tested with safe signed samples. It will remain documented as simulated until owner-provided credentials and an authorized live delivery are available.
9. **Local Python compatibility.** The specification targets Python 3.12+, while the provided workstation has Python 3.10. The package keeps a Python 3.12 container target and uses syntax/dependency bounds compatible with 3.10 so all local quality gates can be executed. This widens compatibility without changing runtime behavior.
10. **Offline frontend assets.** UI inspection prompted removal of a remote font import. The rendered application now uses local system fonts and makes no third-party asset request.
11. **Patched frontend toolchain.** Audits found advisories in React Router v6 and the original Vite/Vitest development toolchain. React Router 7.18.2, Vite 8.2.2, and Vitest 4.1.11 clear the full audit; component, type, build, and Playwright tests pass afterward.
12. **High confidence limitation.** High data confidence requires at least ten authors and all feature families, but not yet persistence across two adjacent windows. The stricter condition is documented and deferred rather than misrepresented.
13. **No guessed Meta version.** The official Meta documentation endpoints could not be reliably fetched during final validation (search returned no results and direct fetches were rejected/rate-limited). `META_GRAPH_VERSION` therefore has no hard-coded default; the owner must set the currently supported version during the dashboard setup checkpoint. Replay and webhook sample ingestion do not depend on it.
