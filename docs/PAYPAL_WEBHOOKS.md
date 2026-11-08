# PayPal webhooks

The listener accepts only signatures verified through PayPal's `verify-webhook-signature` endpoint and requires `PAYPAL_WEBHOOK_ID`. Event IDs are unique in `paypal_webhook_events`; repeats return success without duplicate processing. `CHECKOUT.ORDER.APPROVED` never marks a payment successful. Only a verified `PAYMENT.CAPTURE.COMPLETED` updates the associated request to `SUCCEEDED`.

Subscribe to `CHECKOUT.ORDER.APPROVED`, `PAYMENT.CAPTURE.PENDING`, `PAYMENT.CAPTURE.COMPLETED`, `PAYMENT.CAPTURE.DENIED`, and `PAYMENT.CAPTURE.REFUNDED` using a public HTTPS endpoint. PayPal can retry non-2xx deliveries, so the receiver is intentionally idempotent.
