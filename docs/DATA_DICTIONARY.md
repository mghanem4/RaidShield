# Data dictionary

| Entity | Key data | Privacy notes |
|---|---|---|
| Post | Internal UUID, dataset-scoped hashed source post ID, safe label, counts, timestamps | No original image, caption, or raw source ID |
| Experimental content signal | Safe abstract label scores, threshold, review status, model ID/revision | No input text, inferred identity, intent, or individual reputation |
| Per-comment review evidence | Allowlisted experimental signal, threshold comparison, visible thread context, and deterministic repetition summary | Presentation only; no generated rationale or additional plaintext persistence |
| Event | Dataset-scoped hashed event/comment/parent IDs, full HMAC participant pseudonym, UTC times, fingerprint, optional ciphertext | No raw participant ID; text absent by default |
| Alert | Window, separate coordination/content scores, feature snapshot, explanations, event UUIDs, review state | Group/event-level only |
| Content review | Alert, 0–1 human score, abstract category, note, time | Never contributes to coordination calculation |
| Replay run | Fixture name, counts, status, resulting internal IDs | No submitted files or arbitrary paths |
| Offline import | Safe dataset label, content-origin label, counts, resulting internal IDs | File body, filename, and raw source identifiers are not stored |
| Coordination graph | Graph-local node IDs, short participant labels, weighted behavioral edges, connected-component cluster IDs | Derived on request; full pseudonym digests and comment text are not returned |
| Reply context | Parent availability, reply position/timing, sibling counts, exact/near repetition counts, safe relationship scores and model provenance | Parent/reply plaintext is transient; context is advisory and separate from coordination/content scores |
| Semantic coordination context | Hashed internal neighbor reference, cosine ranking, timing, shared-parent fact, model provenance, threshold | Parent/comment plaintext and embedding vectors are transient; public APIs expose aggregate neighbor evidence without references |

The standard displayed participant label uses the first four hexadecimal characters of the stored 64-character HMAC digest. Graph labels add a graph-local numeric suffix to distinguish rare short-prefix collisions. Offline source IDs are SHA-256 hashed with the dataset name before persistence; they support idempotency and thread reconstruction without retaining supplied identifiers. Participant pseudonyms are not profile-enriched or joined across installations.
