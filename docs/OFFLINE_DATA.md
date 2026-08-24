# Offline data import

RaidShield accepts authorized UTF-8 JSON files in **Test Lab** or through `POST /api/v1/offline/import`. Processing stays on the local machine. The uploaded body and filename are held only for validation and are not retained or logged.

## Format

The file must be no larger than 5 MB and contain between 1 and 1,000 events. Unknown fields are rejected.

```json
{
  "dataset_name": "organizer-safe-evaluation",
  "description": "Optional non-sensitive description",
  "content_origin": "authorized-offline-export",
  "events": [
    {
      "source_event_id": "event-001",
      "post_id": "post-001",
      "comment_id": "comment-001",
      "parent_id": null,
      "participant_id": "participant-001",
      "occurred_at": "2026-08-24T12:00:00Z",
      "text": "SAFE_PLACEHOLDER planning discussion",
      "organizer_review_score": null
    }
  ]
}
```

- `dataset_name`: 1–80 lowercase letters, numbers, `_`, or `-`; it must start with a letter or number. It scopes source-ID hashes, so keep it stable when re-importing the same dataset.
- `description`: optional, 1–500 characters when supplied. Do not put identities or secrets here.
- `content_origin`: 1–80 characters with the same rules as `dataset_name`. Use a non-identifying provenance label.
- `source_event_id`, `post_id`, `comment_id`: required non-empty strings, up to 255 characters.
- `parent_id`: optional source comment ID used to reconstruct replies.
- `participant_id`: required transient identifier. RaidShield immediately replaces it with an installation-keyed HMAC and never persists the supplied value.
- `occurred_at`: timezone-aware ISO 8601 timestamp.
- `text`: required text, 1–10,000 characters. It is discarded after transient analysis unless encrypted storage was explicitly enabled before import.
- `organizer_review_score`: optional number from 0 to 1 representing an independent organizer-provided review signal. It stays separate from the coordination score.

Source event, post, comment, and parent IDs are dataset-scoped SHA-256 hashes before persistence. Re-importing the same dataset is idempotent. Changing `dataset_name` intentionally creates a different identifier scope.

During import, replies are compared with their direct parent and sibling replies while plaintext is still available. RaidShield retains only safe context measurements and optional local-model relationship scores. Parent/reply text is not copied into context metadata, and context does not affect coordination or content-review scores.

When semantic coordination is enabled, the same validated batch is encoded locally before normalized ingestion. Comparisons are limited to different participants on the same post, matching top-level/reply roles, and the configured timing window. Plaintext and vectors are discarded; only abstract pair evidence with hashed internal references is retained.

## Import locally

1. Copy `.env.example` to `.env`, configure the local keys and `ADMIN_TOKEN`, migrate, and start both local servers as described in the README.
2. Open `http://127.0.0.1:5173/test-lab`.
3. Enter the local administrator token and select a `.json` file.
4. Leave **Delete existing local data first** unchecked unless a clean demonstration is intended.
5. Import and open the resulting post or alert links.

For an API-only import:

```bash
curl -sS http://127.0.0.1:8000/api/v1/offline/import \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -F "file=@examples/offline_safe_batch.json;type=application/json" \
  -F "reset_before_import=false"
```

The import endpoint is a local mutation surface, not a public upload service. Keep both servers bound to localhost and import only data you are authorized to process.

The optional model can prioritize content for human review, but its scores are experimental and uncalibrated. Neither a content signal nor a coordination alert proves hate, intent, identity, harm, or a policy violation.
