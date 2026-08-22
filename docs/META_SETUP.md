# Meta setup (owner-controlled)

The replay demo needs no Meta account. The webhook endpoints are implemented and covered by signed synthetic payload tests, but live delivery has not been tested.

Owner steps for an authorized Instagram professional account:

1. Create or select a Meta app in the Meta developer dashboard and add the supported Instagram product for the account-login path you intend to use.
2. Configure a public HTTPS callback ending in `/webhooks/instagram`. A local tunnel may be used only for an owner-controlled test.
3. Generate secrets locally and set `META_VERIFY_TOKEN` and `META_APP_SECRET` directly in `.env`; never paste them into chat or commit them.
4. Configure the same verify token in the dashboard and complete callback verification.
5. Subscribe the app to comment-related webhook fields supported for the selected product and API version.
6. Set `META_ACCESS_TOKEN`, `META_IG_USER_ID`, and `META_GRAPH_VERSION` locally if Graph follow-up reads are later enabled. The MVP does not require follow-up reads for replay or sample webhook ingestion.
7. Use a developer/test account and media owned by that authorized account. Confirm event delivery and inspect only sanitized processing counts.

Development/standard access generally serves app-role accounts. Serving accounts outside app roles can require Live mode, permissions review, business verification, or Advanced Access depending on the current Meta product and permissions. Verify the current requirements in the official Meta dashboard and documentation; approval is not guaranteed.

No scraping, private-message access, profile enrichment, browser automation, or autonomous moderation is implemented.

