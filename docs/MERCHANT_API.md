# Simulated merchant API v1

This local integration contract is not a real railway/food integration. Amounts are integer INR paise. PayPal Sandbox remains separately approved. Payment does not prove booking or delivery.

Operator: run `python -m app.provision_merchants` after migration. It creates `demo-railway` and `demo-food`, returns generated secrets once and stores only SHA-256 hashes. Save secrets in the appropriate merchant server configuration. Re-running refuses to overwrite existing identities. Credentials stay out of browser JavaScript and logs. Use HTTPS beyond localhost. Operators can revoke identity access using its `active` flag; no production onboarding/rotation portal is included.

Every `/api/merchant/v1/...` request requires `X-Merchant-Id` and `X-Merchant-Key`. Wallet login does not grant merchant access. Missing/invalid credentials return 422/401; cross-merchant access returns 404. Creation rate is limited to 30 new requests per merchant per minute. Edge-level abuse protection is required for a public deployment.

`POST /api/merchant/v1/checkout-requests` also requires `Idempotency-Key` (8–160 characters):

```json
{"order_reference":"checkout-001","amount":125000,"currency":"INR","description":"Simulated train ticket","expires_at":"2026-11-10T20:00:00+05:30"}
```

Supply a fresh future expiry within 30 days and an explicit timezone. Reference: 3–160 letters, digits, `_` or `-`; description: 1–500 plain-text characters. Identity and recognition come from authenticated provisioning. Clients cannot set verification, outcomes, callbacks, or extend an existing deadline.

Response: `payment_request_id`, `merchant_order_reference`, `merchant_id`, `merchant`, `amount`, `currency`, `payment_status`, `order_status`, `fulfilled_at`, `expires_at`, relative `review_url`, `mode: SIMULATED`.

Retry an uncertain creation using the SAME key and exact original body, or poll. Changed details or a new key for the same reference return 409. Identical retries preserve the original deadline even after expiry. Bearer credentials are replayable over TLS by design; immutable request idempotency is implemented, not a claimed HMAC/timestamp protocol.

- `GET /checkout-requests/{payment_request_id}`: authoritative owned payment/order state.
- `GET /orders/{reference}`: same state by owned reference.
- `POST /orders/{reference}/fulfillment`: only after confirmed payment; idempotently records separate merchant fulfillment.
- `POST /orders/{reference}/cancel`: cancels an unsubmitted request; submitted/settled payments return 409.

Order states: `PENDING_PAYMENT`, `PAYMENT_PROCESSING`, `PAYMENT_CONFIRMED`, `FULFILLED`, `EXPIRED`, `CANCELLED`, `PAYMENT_FAILED`, `REFUNDED`. Confirmation requires a recorded journal or provider-confirmed capture. Fulfillment is a merchant assertion, not real-world delivery evidence; it remains historically recorded after any refund. Inspect both payment and fulfillment fields.

Polling is the supported merchant result mechanism. No outbound callbacks or merchant-controlled URLs are accepted. There is no new dependency.

See [server-only TypeScript client](../examples/merchant-client/client.ts). Its timeout is an uncertain result; reuse the original creation key/body or query status.

Two terminal examples from the repository root (set only the respective newly provisioned key):

```powershell
$env:MERCHANT_KEY='<demo-railway credential>'
python examples/merchant-client/demo_server.py railway
```

```powershell
$env:MERCHANT_KEY='<demo-food credential>'
python examples/merchant-client/demo_server.py food
```

Open `http://localhost:8091` and `http://localhost:8092`. Each page sends credential-free browser requests to its local Python merchant server, which calls Wallet-Voice on port 8000 with that merchant's credential. Save both checkouts, leave the pages, approve the exact wallet batch, then return to each page to check status and separately confirm simulated fulfillment. Each sample cart is stable during its server process; restarting a sample server starts a new cart. Persisted Wallet-Voice requests remain queryable using their original reference.
