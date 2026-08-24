# Threat model

| Threat | Mitigation |
|---|---|
| Unauthorized import | Local bearer token on the mutation endpoint and localhost-only default binding |
| Duplicate import | Dataset-scoped hashed `source_event_id` and idempotent ingestion |
| Token leakage | Environment variables, `.gitignore`, and no secret logging |
| Participant-identity leakage | Immediate installation-keyed HMAC pseudonymization; source identifiers hashed before persistence |
| Graph identity expansion | Graph API returns graph-local IDs and short display labels, never full stored HMAC pseudonyms or raw participant IDs |
| Comment-content exposure | Disabled persistence by default; local Fernet encryption and retention if enabled |
| Cross-community tracking | A distinct pseudonym key per installation |
| False accusation | Behavioral language, direct feature explanations, and mandatory human review |
| Benign campaign flagged | Independent content score and benign/false-alert resolutions |
| Graph overinterpretation | Visible edge reasons, documented weights, explicit behavioral-only language, and no bot/intent determination |
| Context misinterpretation | Experimental relationship wording, visible provenance/ranking score, mandatory human review, and no effect on alert scores or priority |
| Fabricated model explanation | Template states only the highest label, score, threshold comparison, and deterministic context evidence; UI explicitly says this is not hidden model reasoning |
| Metadata leakage through thread API | Per-comment content signals use a fixed public-field allowlist; text remains hidden unless encrypted storage and administrator access were enabled |
| Semantic embedding leakage | Parent/comment inputs and embedding vectors are never persisted; only hashed internal event references and abstract pair measurements remain, and public thread APIs remove the references |
| Common-language false coordination | Semantic similarity cannot create a graph edge alone; it requires timing, exact-text, or shared-thread corroboration and explicit human review |
| Model false positive or target confusion | Disabled by default; experimental labeling; abstract categories; visible provenance and scores; human override; no autonomous action |
| Model supply-chain or runtime network access | Immutable revision, safetensors-only loading, explicit one-time cache step, and local-files-only runtime default |
| Plaintext leakage during inference | In-process local inference before encryption/discard; no input logging; only safe scores and provenance persist |
| Parent/reply context leakage | Parent and sibling text stays in excluded transient fields; only structural facts and abstract relationship scores persist or export |
| Malicious offline file | Strict JSON schema, UTF-8 decoding, forbidden extra fields, 5 MB/1,000-event bounds, no retained filename or raw body |
| Fixture path traversal | Only enumerated bundled fixtures; no arbitrary fixture path |
| Formula injection | No CSV export; escaped HTML and structured JSON |
| Stored XSS | React escaping and HTML escaping in evidence reports |
| Denial of service | 5 MB/1,000-event import limits, bounded two-minute detection queries, limited list results |
| Unauthorized deletion/settings | Bearer token plus explicit deletion confirmation |
| Profile surveillance expansion | No profile client or profile fields in domain models |

Remaining production risks include uncalibrated multilingual model behavior, model and dependency supply chain, macOS swap/backups, single-token administration, an in-process background task, no rate limiter, no tenant isolation, and local key lifecycle. Do not expose the MVP directly to the public internet.
