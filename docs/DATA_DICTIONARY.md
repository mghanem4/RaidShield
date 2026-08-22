# Data dictionary

| Entity | Key data | Privacy notes |
|---|---|---|
| Post | Internal UUID, source media ID, safe label, counts, timestamps | No original image or caption |
| Event | Source event/comment IDs, parent ID, full HMAC pseudonym, UTC times, fingerprint, optional ciphertext | No raw username; text absent by default |
| Alert | Window, separate coordination/content scores, feature snapshot, explanations, event UUIDs, review state | Group/event-level only |
| Content review | Alert, 0–1 human score, abstract category, note, time | Never contributes to coordination calculation |
| Replay run | Fixture name, counts, status, resulting internal IDs | No submitted files or arbitrary paths |

The displayed participant label uses the first four hexadecimal characters of the stored 64-character HMAC digest. Source IDs support idempotency and thread reconstruction; they are not profile-enriched or joined across installations.

