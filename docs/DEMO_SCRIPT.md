# Demo script

1. Start from migrated local storage and open `http://127.0.0.1:5173`.
2. Open **Test Lab**, enter the locally configured `ADMIN_TOKEN`, and replay `normal_discussion`. Open its post and note that no coordination alert exists.
3. Replay `single_review_comment`; explain that an independently labelled comment is not treated as coordination.
4. Replay `coordinated_benign_burst`; open the medium alert and show separate scores.
5. Replay `reply_thread_burst`; open the alert, feature bars, and reconstructed parent with 12 replies.
6. Mark it **benign coordination** and export the redacted ZIP.
7. Optionally replay `coordinated_review_burst` to show that high priority requires both coordination indicators and an independent content-review score.

Narrative: “RaidShield does not decide who is hateful. It detects explainable changes in how a protected account is being engaged, reconstructs reply patterns, and helps a human moderator review and preserve evidence safely.”

