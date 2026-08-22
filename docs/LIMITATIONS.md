# Known limitations

- Live Instagram webhook delivery is not verified without owner-controlled credentials and an authorized professional account. Only signed safe samples are tested.
- The Instagram adapter intentionally covers the documented comment-style payload shape used in tests; Meta product/version variants must be validated during owner testing.
- SQLite, one local admin token, and in-process background tasks are local-MVP choices, not public deployment architecture.
- With raw-text storage disabled, near-duplicate analysis uses a bounded in-process transient cache. A process restart discards that cache, as intended; historical similarity cannot be recomputed from fingerprints alone.
- Confidence is data-sufficiency language. The MVP does not yet require persistence across two adjacent windows for “high”; this conservative production refinement is deferred.
- No cross-post overlap feature is included. It was optional and deferred until core outcomes are stable.
- No rate limiter or pagination cursor is implemented. List endpoints are capped; the two-minute detector remains bounded.
- The app cannot see direct messages, private activity, deleted events it never received, or activity outside an authorized comment surface.
- Coordination indicators can flag benign campaigns. They do not establish intent, harm, a policy violation, or a legal conclusion.

