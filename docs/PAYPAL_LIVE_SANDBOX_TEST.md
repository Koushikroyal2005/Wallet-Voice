# Manual PayPal Sandbox test

## Current integration and local verification

Observed on 2026-11-10 for this working-tree revision: 101 local tests passed, 15 PostgreSQL tests skipped in the local run. The two new PayPal concurrency tests were then executed against the isolated PostgreSQL container and passed (exit code 0); the remaining 13 integration/migration tests were not executed because their fixtures/reset command conflict with the no-reset instruction. TypeScript/Vite build passed. Existing four-viewport browser verification passed. Seven new PayPal browser fixture journeys passed: completion, denial, pending-to-denied, lost capture response, buyer cancellation, reload of a pending capture, and reload after a lost capture response. These also check SDK initialization and duplicate approval callbacks. No live provider checks, Sandbox buyer approval, capture or webhook delivery were performed in this revision; an authenticated test buyer was not available to this task. Private credentials were neither inspected nor changed.

The browser uses SDK v6 `createInstance({clientId, components: ["paypal-payments"]})`, checks eligibility, and passes an order promise resolving to `{orderId}` to the one-time session. Buyer approval invokes server capture; approval itself is not a successful payment. This follows the current [PayPal SDK setup](https://developer.paypal.com/sdk/js/set-up/) and [Orders v2](https://developer.paypal.com/api/orders/v2) documentation.

Create and capture retain stable, distinct idempotency keys. Create retries freeze the original provider amount and payload in server-owned request metadata. Unresolved creation older than five hours, or a legacy claim without a frozen payload, requires manual reconciliation; it is not automatically replaced with a new charge. See [PayPal idempotency](https://developer.paypal.com/api/rest/reference/idempotency/).

`POST /api/paypal/orders/{order_id}/refresh` performs provider GET reconciliation only. Pending capture polling is sequential and bounded; Reconnect resumes the recorded order. A lost capture response triggers GET reconciliation. Pending/unknown results never debit internal funds or claim success. Capture completion requires a capture ID, status, and matching amount/currency. Webhooks use PayPal's server signature-verification endpoint; missing headers fail closed. Verified early events are replayed when the local order is saved. Full refund events are supported; partial-refund accounting remains outside this phase.

Run local checks from the indicated directories:

```powershell
# backend (use test-only configuration; no live credentials)
python -m pytest -q tests/test_paypal.py tests/test_product_flows.py
# frontend
npm.cmd run build
node scripts/verify-product.mjs
node scripts/verify-paypal.mjs
```

The browser checks mock SDK/API responses; they are not proof of provider connectivity. The new PostgreSQL tests use fresh schemas and no reset commands:

```powershell
# repository root; separate project, test-db only, no development volume
docker compose -p walletvoice-paypal-verification -f docker-compose.yml -f docker-compose.test.yml --profile test up -d --no-deps test-db
docker compose -p walletvoice-paypal-verification -f docker-compose.yml -f docker-compose.test.yml --profile test build test
docker compose -p walletvoice-paypal-verification -f docker-compose.yml -f docker-compose.test.yml --profile test run --rm --no-deps test python -m pytest -q tests/integration/test_paypal_lifecycle.py
```

This explicitly overrides the existing test service command, which otherwise resets its schema. It covers concurrent creation/capture and duplicate webhook delivery with independent PostgreSQL sessions and mocked provider calls. The original financial/migration integration suite remains separate; these checks do not replace it.

## Live buyer journey

1. In the PayPal Developer Dashboard, create Sandbox business and personal accounts and a REST app. Copy the app Client ID and Secret.
2. Put those values plus the REST-app webhook ID in `.env`; set `PAYPAL_ENABLED=true`, `PAYPAL_MODE=sandbox`, and keep `PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com`.
3. Start the app with `docker compose up --build` and confirm `GET /api/paypal/config` reports `configured: true`. Run `python scripts/test_paypal_connections.py`; it checks OAuth only.
4. Make the webhook endpoint publicly HTTPS-reachable, for example with a secure HTTPS tunnel or deployed URL: `https://your-host/api/webhooks/paypal`. Subscribe it to the capture/order events documented in `PAYPAL_WEBHOOKS.md`, then copy the returned webhook ID into `.env` and restart.
5. In Payment Inbox, generate a Railway request and choose **PayPal Sandbox**. Verify the original INR amount and explicit USD Sandbox representation, then approve with the Sandbox personal buyer account.
6. Confirm the Inbox shows the authoritative capture status and capture reference. Verify `GET /api/wallet` has not changed and `/api/paypal/payments` contains the external transaction.
7. In the PayPal dashboard/Webhooks event log, confirm delivery of a real Sandbox capture event and match its event/order/capture IDs to the stored result. The webhook simulator is not supported by this adapter's postback signature verification; use real Sandbox events and their dashboard resend action. See [PayPal webhook verification](https://developer.paypal.com/api/rest/webhooks/rest/).
8. Resend the same real event and confirm one stored event and no additional financial entries. Close/reopen checkout while waiting for approval. Reload during pending processing. Confirm pending or denied never appears as completed.
9. Compare posted, reserved and available wallet balances, reservation count and journal count before and after checkout. All must remain unchanged. Record the exact timestamp, application revision and provider identifiers in private test evidence; never include credentials, tokens or buyer passwords.

Never use production credentials while `PAYPAL_MODE=sandbox`, and never put the Client Secret in frontend code.

## Fresh-install login and license

`.env.example` keeps sign-in enabled. Before starting a fresh install, generate a private session secret as described in README and set it locally. Missing/short secrets fail configuration validation without printing credential inputs. Duplicate NVIDIA keys and unused example variables were removed; private `.env` values are never changed by this phase.

No repository LICENSE file was found. The [PayPal AI Hackathon official rules](https://paypalaihackathon.devpost.com/rules), checked on 2026-11-10, require a public repository with a detectable open-source license file. They do not name a specific license in that submission requirement. The owner must confirm the license before a LICENSE file is added; none has been selected or added in this phase. Dependency licenses do not select a license for this application.
