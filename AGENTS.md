# Repository Instructions

- Treat `RaidShield_MVP_Build_Spec.md` as authoritative.
- Preserve the safety language: indicators require human review and do not prove intent or a policy violation.
- Never persist or log raw usernames, secrets, raw webhook bodies, or unencrypted comment text.
- Keep replay and Instagram input behind adapters and route both through the same normalized ingestion service.
- Keep coordination and content-review scores separate.
- Use migrations for schema changes and update `docs/STATUS.md` and `docs/DECISIONS.md` after material changes.

