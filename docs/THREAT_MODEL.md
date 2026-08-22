# Threat model

| Threat | Mitigation |
|---|---|
| Forged webhook | HMAC-SHA-256 verification over the raw body before JSON parsing |
| Webhook replay | Unique `source_event_id` and idempotent ingestion |
| Token leakage | Environment variables, `.gitignore`, and no secret logging |
| Username leakage | Immediate installation-keyed HMAC pseudonymization |
| Comment-content exposure | Disabled persistence by default; local Fernet encryption and retention if enabled |
| Cross-community tracking | A distinct pseudonym key per installation |
| False accusation | Behavioral language, direct feature explanations, and mandatory human review |
| Benign campaign flagged | Independent content score and benign/false-alert resolutions |
| Malicious fixture upload | Only enumerated bundled fixtures; no arbitrary path or upload |
| Formula injection | No CSV export; escaped HTML and structured JSON |
| Stored XSS | React escaping and HTML escaping in evidence reports |
| Denial of service | 1 MB webhook limit, bounded two-minute detection queries, limited list results |
| Unauthorized deletion/settings | Bearer token plus explicit deletion confirmation |
| Profile surveillance expansion | No profile client or profile fields in domain models |

Remaining production risks include single-token administration, an in-process background task, no rate limiter, no tenant isolation, and local key lifecycle. Do not expose the MVP directly to the public internet.

