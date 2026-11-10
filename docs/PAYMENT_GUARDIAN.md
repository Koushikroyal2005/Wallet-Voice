# Payment Guardian

The assistant and Payment Inbox share `PaymentGuardian`. Preparing a review never executes a payment. The user chooses a source and explicitly confirms the wallet payment or approves the PayPal Sandbox checkout. Unknown businesses require acknowledgement. Held requests can be released through the existing release route.

The read-only `GET /api/payments/{payment_id}/review` returns the existing manual policy evaluation, the evaluation after explicit merchant acknowledgement, configured wallet currency and per-payment limit, the latest attempt, recorded PayPal state and settlement references. It rolls back the read transaction, including any default objects initialized by existing policy helpers. Execution still rechecks policy under the existing locks. No journal, reservation, authorization or provider behavior was changed.

The panel polls this snapshot every three seconds while mounted. Existing application SSE continues to refresh the inbox and wallet. Source selection locks once an attempt owns the request or a PayPal order exists. The same wallet idempotency key survives retries and is shared across inbox and assistant reviews. Cancel closes an unsubmitted review; it does not reverse a payment or cancel a provider order. Processing results remain pending until the backend records an outcome.

Wallet completion requires a successful request and a posted journal reference. PayPal completion requires the recorded completed capture and capture ID. Receipts distinguish simulated wallet records from PayPal Sandbox records. Times are labelled as capture recorded, journal posted or record timestamp; an attempt creation timestamp is never represented as a settlement timestamp. External reviews explicitly explain that internal wallet limits do not apply.

## Files changed in this phase

- `backend/app/main.py`: added the minimal read-only review endpoint using existing policy and settlement records.
- `frontend/src/components/PaymentGuardian.tsx`: shared review, source selection, explanation, timeline, actions, status refresh and receipt.
- `frontend/src/App.tsx`: reused Guardian in the Payment Inbox dialog and removed its duplicate review controls.
- `frontend/src/components/VoiceAssistantPanel.tsx`: reused Guardian for payment previews; other assistant previews retain their existing approval controls.
- `frontend/src/design.css`: responsive Guardian layout and visible keyboard focus.
- `backend/tests/test_guardian.py`: review and approval contract tests for wallet success, duplicate confirmation, failure, unknown merchant, balance, expiry, hold and external records.
- `backend/tests/integration/test_guardian_review.py`: actual PostgreSQL duplicate confirmation and journal receipt check in a fresh schema.
- `frontend/scripts/guardian-fixture.mjs`: shared explicit browser fixtures.
- `frontend/scripts/verify-guardian.mjs`: eight browser scenarios with desktop/mobile overflow and duplicate-click checks.
- `frontend/scripts/verify-product.mjs`, `verify-voice.mjs`, `verify-paypal.mjs`: adapted existing checks to the shared review endpoint and UI.
- `docs/PAYMENT_GUARDIAN.md`, `docs/TESTING.md`: feature behavior and measured verification.

## Verification — 10 November 2026

- Backend regression: 167 passed; 17 PostgreSQL tests skipped without `TEST_DATABASE_URL`.
- Isolated PostgreSQL: 4 passed (Guardian duplicate confirmation, two PayPal lifecycle races, assistant race). Fresh schemas on the dedicated tmpfs test database; no reset command or development volume used.
- Frontend TypeScript/Vite production build: passed.
- Existing product browser verification: passed at four viewport sizes, including funding, recipient draft, permissions and stale assistant preview checks.
- Existing voice browser verification: 7 fixture journeys passed.
- Existing PayPal SDK browser verification: 7 fixture journeys passed.
- Guardian browser verification: 8 fixture scenarios passed, including all requested payment outcomes and duplicate clicks.
- Python compilation: passed.
- Live provider calls, physical microphone, actual Sandbox buyer approval/capture/webhook delivery: unexecuted in this phase. Browser provider states are fixtures; PostgreSQL provider calls are mocked. These results do not prove a real PayPal payment occurred.

The default Compose test command invokes a destructive reset script and was not used. A command override ran only fresh-schema integration tests. The other 13 PostgreSQL financial/migration tests were not executed in this phase.

## Manual acceptance

1. Open a fresh existing request through the Inbox, then through the assistant. Check the same merchant, exact amount/currency, deadline and verification record.
2. Review the server's wallet explanation; test a request exceeding balance or limits. Confirm the action stays blocked.
3. For a permitted demo wallet request, confirm once. Check the journal reference, status and labelled timestamp; revisit through the Inbox to see the same record.
4. Switch a fresh request to PayPal Sandbox, review the converted provider amount, approve with a Sandbox buyer and inspect pending/capture results. Confirm the internal wallet did not change and check the real webhook delivery separately.
5. Test unknown merchant acknowledgement, hold/release, expired request and provider failure. Tab through each control and repeat at 390px width.

No new dependencies, credential changes, commits or pushes were made.
