# AI Wallet — 2–3 minute demo

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
