# Wallet-Voice V2 checklist

- [x] Global AutoPay requires a valid merchant mandate backed by matching consumed PIN authorization; reservation rechecks under locks, daily allowance and idempotency remain enforced.
- [x] Bounded timezone-aware legacy checkout deadlines; immutable retry values; awaiting approval is not an explicit user hold.
- [x] Ready-for-review notice and shared refund/cancellation/partial status labels.
- [x] Per-recipient acknowledgement creates a new immutable review, cancels the old review, preserves unverified identity.
- [x] Reminder off/on re-arms cancelled stages while retaining device delivery markers.
- [x] Additive merchant identity/order migration, two provisioned identities, hashed credentials, constant-time checks, ownership, input/rate bounds, immutable reference/key, no callback URLs.
- [x] Versioned creation/status/cancel/fulfillment API with journal/provider-backed payment evidence.
- [x] Server-only typed client and two local independently authenticated merchant examples.
- [x] Voice food/kitchen aliases, corrections, backend order-state answers, waiting/expiry questions and reminder postponement.
- [x] Saved/expired merchant checkouts in Attention and separate fulfillment explanation in Guardian.
- [x] Actual FastAPI HTTP/isolated database merchant journey; PostgreSQL concurrent ingestion test.
- [ ] Live rebuilt two-merchant demo with operator credentials: manual verification remains.
- [ ] Physical microphone, live NVIDIA, actual OS push and PayPal buyer approval: not executed in this phase.

No commit/push, private credential edits or development database resets. Results below are measured only; fixture providers are not live evidence.

Limits: single-owner demo; polling and static server-side merchant credentials; no public onboarding/rotation portal, outbound callbacks or real merchant fulfillment. Local example cart memory resets on example-server restart; saved wallet requests remain durable. Reminder postponement affects eligible background reminders only, keeps the request in Attention, never extends expiry or authorizes payment, and requires notifications to be enabled for delivery.

## Verification, 2026-11-10

- PASSED: affected financial/merchant baseline, 28 tests; merchant/HTTP regression run, 16 tests; final worker/merchant/payment regression run, 26 tests plus the added legitimate worker scenario individually passing. Final complete isolated PostgreSQL integration run: 27 tests, including migrations, synchronized ingestion, PIN-bound batches, automatic-mandate daily-limit races, duplicate reservations, legitimate recovery and rejection/release of unauthorized legacy AutoPay claims.
- Full backend run in the existing test dependency image: 229 PASSED, 1 FAILED, 1 SKIPPED. The failure was a harness mount omission: `test_example_configuration_has_unique_keys` expected `/.env.example`. Re-running that test with only the public template mounted read-only PASSED. No application failure remains from that run. Subsequent focused tests cover the final public legacy-key guard. The skip was the optional `pywebpush` adapter absent from this older dependency image; a fresh application build installs existing requirements.
- PASSED: TypeScript/Vite production build; standalone TypeScript merchant client type-check; Python compilation; Compose configuration validation; `git diff --check` (line-ending warnings only).
- PASSED: product Playwright, 5 screens/4 widths (1440/1024/768/390), 7 interaction groups. Guardian 9 scenarios including refund; voice 7 fixture journeys; PayPal 7 fixture journeys.
- PASSED: `verify-v2.mjs`, real local FastAPI/SQLite API, two credentialed merchants, immutable retries, actual API process restart, saved Attention, conversational batch, 1440/390 review, duplicate clicks, one PIN, two journal receipts, wallet reconciliation, merchant polling and separate fulfillment. Both actual Python merchant checkout pages exercised at 390px. NVIDIA/PayPal are disabled in this test; conversational input is typed.
- Captured and inspected `artifacts/v2-review/merchant-review-1440.png`, `merchant-review-390.png`, and `railway-checkout-390.png`. Receipts and both local merchant page screenshots are in that ignored directory.
- Initial Windows sandbox tests encountered temporary-directory permission errors and were interrupted. Re-runs used fresh isolated workspace test directories or the dedicated test image. No development database was used.
- NOT EXECUTED: physical microphone, live NVIDIA inference, actual OS push delivery, PayPal buyer approval/capture, fresh application Docker image build. These cannot be inferred from fixture success.

## Changed files and purposes

- `backend/app/services.py`: mandate-only automatic reservations, allowance accounting and unsubmitted cancellation transition.
- `backend/app/execution.py`: reject and release resumed legacy AutoPay claims without current PIN-backed mandate authority.
- `backend/app/agentic.py`: consumed mandate evidence, read/lock distinction, factual order intent and follow-up selection.
- `backend/app/main.py`: versioned router/auth boundary, disabled public legacy placeholder key, checkout deadlines and merchant fulfillment review data.
- `backend/app/merchants.py`: merchant provisioning/authentication, immutable ingestion, scoped authoritative status, cancel and fulfillment.
- `backend/app/models.py`, `backend/alembic/versions/20261111_merchants_v2.py`: additive merchant identity/order persistence.
- `backend/app/provision_merchants.py`: operator-only one-time credential provisioning.
- `backend/app/payment_batches.py`, `backend/app/batch_routes.py`: per-recipient acknowledgement bound into a replacement snapshot.
- `backend/app/reminders.py`: re-arm on preference changes and saved/expired merchant Attention items.
- `backend/app/batch_voice.py`, `backend/app/context.py`, `backend/app/voice.py`: matching, corrections, factual merchant status and reminder postponement.
- `backend/scripts/serve_v2_verification.py`: fresh isolated test API with explicit process-restart support.
- `backend/tests/test_merchants_v2.py`, `backend/tests/integration/test_merchants_v2_postgres.py`: merchant/security/approval/deadline/notification/fulfillment and race coverage.
- `backend/tests/test_domain.py`, `backend/tests/test_product_flows.py`, `backend/tests/integration/test_postgres_financial.py`, `backend/tests/integration/test_product_concurrency.py`: update reservation-only tests to manual service mode; mandate scenarios now include consumed PIN evidence; global switch alone is rejected.
- `frontend/src/App.tsx`: core product copy and truthful review notice.
- `frontend/src/components/AttentionQueue.tsx`: understandable saved/urgent/expired labels.
- `frontend/src/components/PaymentBatchReview.tsx`: acknowledgement action, new review identity, readable states and explicit authenticated-demo trust label.
- `frontend/src/components/PaymentGuardian.tsx`: separate merchant fulfillment details, shared status labels.
- `frontend/src/components/Workspace.tsx`: local demo links and settlement-versus-fulfillment activity explanation.
- `frontend/src/lib/formatting.ts`: shared refund/review/partial/cancel labels.
- `frontend/scripts/verify-v2.mjs`: actual local merchant-to-wallet/restart/mobile journey.
- `frontend/scripts/verify-guardian.mjs`: explicit refunded-state regression.
- `examples/merchant-client/client.ts`, `examples/merchant-client/demo_server.py`: server-only native-fetch client and two local credentialed merchant checkout servers.
- `README.md`, `docs/MERCHANT_API.md`, `docs/DEMO_SCRIPT.md`, `docs/TESTING.md`, `IMPLEMENTATION_STATUS.md`, this checklist: contract, setup, demo, measured validation and limits.
