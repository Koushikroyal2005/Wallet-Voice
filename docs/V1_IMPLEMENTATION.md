# Wallet-Voice V1 implementation checklist

Implemented locally; no commit or push performed.

- Phase 1: HTML5 metadata, refund synchronization (attempt/request/order/receipt), historical capture references retained, persistent Guardian action errors, current screenshot navigation/authentication.
- Phase 2: automatic assistant submission by default after explicit recording/end-of-speech; opt-in transcript review, visible/editable transcript, cancellation/cleanup/retry keys retained; provider details collapsed, playback opt-in.
- Phase 3: durable exact batch/item entities, snapshot hashes and expiry; backend phrase/ordinal resolution, exclusions, correction, ambiguity; atomic reservations; transaction-bound PIN; protected single-payment route; per-item journal receipts and partial/pending states. Legacy batch execution rejects requests without the new approval flow.
- Phase 4: INR 100,000 aggregate posted-wallet credit ceiling in journal posting under wallet lock; existing ledger preserved; shortfall in reviews; PIN-protected simulated incoming bank example.
- Phase 5: durable deadline reminder records, unique request/stage, preferences/quiet hours, worker dispatch with row claiming and retry, SSE attention refresh, exact request links, manifest/service worker, browser subscriptions and VAPID delivery adapter.
- Phase 6: original navy/coral design retained; exact payment sheet, contextual attention, compact voice preferences, explicit simulated/Sandbox/refunded states, mobile layouts.
- Phase 7: focused backend tests, real PostgreSQL races and migration, browser fixtures, actual FastAPI/SQLite browser journey with synthetic microphone transcription. See TESTING.md for measured results.
- Phase 8: README, testing instructions, demo script and limitations documented.

## Limits requiring manual verification

- Real microphone/end-of-speech quality, NVIDIA Whisper/Nemotron/TTS and live PayPal buyer approval/capture/webhook were not exercised during V1 implementation. No private .env credentials were read.
- Web Push delivery requires operator-supplied VAPID keys, HTTPS or localhost, supported browser, explicit permission and a saved subscription. Real OS notification delivery is unverified. Web Push acceptance is not proof a user saw the notification.
- Push uses the same notification tag on retries. Successful subscriptions are not resent during an ordinary retry. A process crash after sending but before commit can cause an at-least-once redelivery. Quiet hours defer delivery; request status is rechecked before dispatch. Generic notification text does not disclose merchant/amount on the lock screen. Reminders expire with the request, including previously queued pushes via a short TTL.
- Audio is uploaded to configured NVIDIA transcription before its words are known. The existing secret guard prevents recognized PIN/OTP text from reaching model inference/storage; it cannot guarantee that a spoken secret never reaches the speech transcription service. Never speak secrets. PIN entry is local secure input and goes only to the wallet authorization API.
- The PWA does not listen in the background and does not provide guaranteed background speech, offline payment, or native app behavior. No financial API response is cached by the service worker.
- The app remains a single-owner demo. Bank transfers and wallet payments are simulations; PayPal is Sandbox. No real bank, UPI, IRCTC or food-order fulfillment integration exists.
- Repository LICENSE is absent; owner selection is required before claiming open-source licensing.

## New dependency

`pywebpush` handles standards-based payload encryption and VAPID signing. Implementing cryptography directly would introduce unnecessary security risk. Adapter usage follows the [maintainer documentation](https://github.com/web-push-libs/pywebpush). Its live delivery path remains unverified until configured.
