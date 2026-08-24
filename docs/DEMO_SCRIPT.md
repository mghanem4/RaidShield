# Demo script

1. Start from migrated local storage and open `http://127.0.0.1:5173`.
2. Open **Test Lab**, enter the locally configured `ADMIN_TOKEN`, import `examples/offline_safe_bot_raid_demo.json`, and show that the harmless dataset was validated and processed without uploading it to an external service.
3. Replay `normal_discussion`. Open its post and note that no coordination alert exists.
4. Replay `single_review_comment`; explain that an independently labelled comment is not treated as coordination.
5. Replay `coordinated_benign_burst`; open the medium alert and show separate scores.
6. Replay `reply_thread_burst`; open the alert, feature bars, coordination graph, and reconstructed parent with 12 replies. Expand a reply's context panel to show its parent timing, position, and harmless sibling repetition. Drag a node, zoom, arrange the remaining nodes, then explain the selected node's strongest connections and reply-context summary.
7. Mark it **benign coordination** and export the redacted ZIP.
8. Optionally replay `coordinated_review_burst` to show that high priority requires both coordination indicators and an independent content-review score.

Narrative: “RaidShield does not decide who is hateful. It detects explainable patterns in an authorized offline dataset, reconstructs reply activity, and helps a human moderator review and preserve evidence safely.”

Graph narrative: “Each node is a pseudonymous participant. A thicker line means stronger combined behavioral evidence, and color shows a connected cluster. The graph does not prove these participants are bots or controlled by one actor.”

Context narrative: “Each reply is compared with its parent and siblings before text is discarded. Structural repetition is deterministic; any model relationship is an experimental ranking that can be wrong and never changes the raid score.”

When an organizer-authorized offline dataset has model metadata, expand **Model review evidence** beneath a comment. Point out the comment/parent context, all label rankings, configured threshold, and sibling comparison. Read the calculation summary as a description of the score comparison—not as an explanation of hidden model reasoning.

With semantic context enabled, import the harmless offline example and expand **semantic-context matches** under a reply. In the graph inspector, show that differently worded activity can connect through similar `parent + reply` meaning plus timing/thread evidence. Emphasize that semantic similarity alone cannot create an edge and does not prove coordination or automation.

Optional detector narrative: “This disabled-by-default local model surfaces an experimental content-review signal. The score is not a probability or determination, stays separate from coordination, and can be corrected by a moderator. Arabizi and multilingual performance are not claimed until evaluated on organizer-approved material.” Do not add harmful examples to repository fixtures merely to demonstrate the model.
