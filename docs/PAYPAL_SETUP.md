# PayPal Sandbox setup

Create a PayPal Developer REST app, then create Sandbox business (merchant) and personal (buyer) accounts. Put the REST app Client ID and Secret in `.env`; keep `PAYPAL_ENABLED=false` until both are present. Set `PAYPAL_ENABLED=true`, retain `PAYPAL_MODE=sandbox`, and restart the backend.

The frontend receives only the public Client ID through `/api/paypal/config` and a short-lived browser client token through the backend-only `/api/paypal/browser-client-token` endpoint required by the current JavaScript SDK v6. It never receives the secret or the reusable server OAuth token. Run `python scripts/test_paypal_connections.py` to check OAuth only; it does not create or capture an order.

To receive real Sandbox webhooks, expose `/api/webhooks/paypal` through a public HTTPS tunnel or deployment URL, subscribe the REST app to checkout/capture events, and set `PAYPAL_WEBHOOK_ID`. Use the PayPal webhook simulator only to test delivery/signature handling; it is not proof of a real buyer checkout.

Official references: https://developer.paypal.com/sdk/js/set-up/ and https://developer.paypal.com/api/rest/integration/orders-api/.

For an exact buyer-approval and webhook verification walkthrough, see [manual Sandbox test](PAYPAL_LIVE_SANDBOX_TEST.md).
