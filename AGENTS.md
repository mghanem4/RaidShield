# Repository Instructions

- Treat `RaidShield_MVP_Build_Spec.md` as authoritative.
- Preserve the safety language: indicators require human review and do not prove intent or a policy violation.
- Never persist or log raw participant identifiers, secrets, raw import bodies, filenames, or unencrypted comment text.
- Keep bundled replay and offline JSON input behind adapters and route both through the same normalized ingestion service.
- Keep coordination and content-review scores separate.
- Use migrations for schema changes and update `docs/STATUS.md` and `docs/DECISIONS.md` after material changes.
