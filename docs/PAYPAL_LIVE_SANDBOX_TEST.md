# Manual PayPal Sandbox test

1. In the PayPal Developer Dashboard, create Sandbox business and personal accounts and a REST app. Copy the app Client ID and Secret.
2. Put those values plus the REST-app webhook ID in `.env`; set `PAYPAL_ENABLED=true`, `PAYPAL_MODE=sandbox`, and keep `PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com`.
3. Start the app with `docker compose up --build` and confirm `GET /api/paypal/config` reports `configured: true`. Run `python scripts/test_paypal_connections.py`; it checks OAuth only.
4. Make the webhook endpoint publicly HTTPS-reachable, for example with a secure HTTPS tunnel or deployed URL: `https://your-host/api/webhooks/paypal`. Subscribe it to the capture/order events documented in `PAYPAL_WEBHOOKS.md`, then copy the returned webhook ID into `.env` and restart.
5. In Payment Inbox, generate a Railway request and choose **PayPal Sandbox**. Verify the original INR amount and explicit USD Sandbox representation, then approve with the Sandbox personal buyer account.
6. Confirm the Inbox shows the authoritative capture status and capture reference. Verify `GET /api/wallet` has not changed and `/api/paypal/payments` contains the external transaction.
7. In the PayPal dashboard/Webhooks event log, confirm delivery. A simulator delivery only tests verification/deduplication; it does not replace a buyer approval/capture test.

Never use production credentials while `PAYPAL_MODE=sandbox`, and never put the Client Secret in frontend code.
