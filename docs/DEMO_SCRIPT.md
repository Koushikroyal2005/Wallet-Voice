# Wallet-Voice V1 — reproducible demo

1. Run `docker compose up --build -d` and `docker compose exec api python -m app.demo`. Existing ledger rows remain intact. The seed opening top-up is idempotent; existing merchant deadlines are not reset. Use fresh pending requests; never erase a development database for a presentation.
2. Unlock the wallet with its configured PIN. Keep AutoPay off. Show the saved train, movie, electronics and food requests. Explain that these are demo requests, not real bookings or fulfillment.
3. Let the worker run a pass (normally every 10 seconds). Open **Remembered for you**, then **Review now** on a deadline reminder. This opens the exact request. OS push is a separate optional setup, not assumed evidence.
4. Choose **Talk to your wallet**, ask “Which payments are urgent?” and pause. With NVIDIA configured, recording ends on silence, transcribes and submits automatically. With no speech credentials, use **Type instead** and explain the deterministic mode in Assistant details.
5. Say/type “Pay the train and movie tickets, not the food order.” Show the exact two items, deadlines, verified/unrecognized labels, simulated wallet source, total and projected balance. Try “Remove the movie ticket” and then prepare the two-item review again to demonstrate correction.
6. Enter the demo wallet PIN in the review form, never in speech/chat. The approval is bound to this immutable snapshot. No extra request can be added. Complete the payment and show individual journal receipts. Food remains pending. A failed item produces PARTIAL or FAILED, never a fabricated all-success result.
7. Open Wallet and show posted/reserved/available amounts and activity. If a review has insufficient funds, show its exact shortfall, cancel/review later, and choose **Add demo money** or **Receive ₹500 demo bank transfer**. Both are simulated bank top-ups and require PIN approval. The aggregate posted balance cannot exceed ₹1,00,000.
8. Separately prepare ONE fresh request with PayPal Sandbox. The buyer must approve through PayPal. Only backend-confirmed capture is shown as completed. Compare the internal wallet balance before/after; PayPal never reserves/debits it. If credentials or buyer access are unavailable, say this journey is unverified and show the unavailable state.

For repeatable automated evidence, run `node scripts/verify-v1.mjs` from frontend. It starts a fresh isolated actual FastAPI/SQLite server, uses a synthetic microphone transcript, and validates settlement/receipts; it is not live NVIDIA or PayPal evidence.

## Earlier individual PayPal demonstration

## Primary path (credentials available)

1. Open `http://localhost:8080`. Explain that **available** balance is posted balance less reservations, and that all bank movements are simulated.
2. Open Payment Inbox. Click the three merchant simulator buttons, or use the seeded Railway, CinemaPass, and ElectroHub requests. Railway expires first and is therefore urgent.
3. On the overview, type or say: **“Which payments are urgent?”** The response is based on the backend deadline policy, not an invented AI answer.
4. Say: **“Pay my train ticket using PayPal.”** Review the selected merchant, amount, deadline, and external PayPal Sandbox source. No money moves yet.
5. Click the PayPal Sandbox action, approve as a Sandbox buyer, and wait for backend capture. Show that the Inbox updates and that the wallet balance did not change.
6. Generate or select a second eligible request. Choose **Pay with AI Wallet**, confirm it, then show the lower available balance, reservation/payment result, and transaction history.
7. Open AutoPay controls and point out the master switch and time-sensitive-only safeguard. Finish by showing that the batch preview is dry-run only.

## Backup path (no provider credentials/network)

Use typed voice commands for balance, urgent requests, and batch evaluation. Explain that NVIDIA fields are intentionally disabled and the UI uses its demo parser/browser speech fallback. Show the PayPal Sandbox panel reporting unavailable instead of claiming checkout. Complete the internal AI Wallet demo payment and show its journal-backed balance change.

Never claim that a PayPal or NVIDIA action succeeded unless the provider response is visible. See [manual Sandbox test](PAYPAL_LIVE_SANDBOX_TEST.md) before recording a real checkout.
