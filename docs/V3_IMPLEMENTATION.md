# V3 implementation checklist

Implemented in the existing modular monolith. No commit/push, new runtime dependencies or development database reset. Private `.env` remains untouched. All internal funds and merchant demos are simulated; PayPal Sandbox remains separate.

- [x] Separate persistent payment memory from reminder preferences; dismiss/snooze/restore without changing financial state; deadline-derived priority.
- [x] Shared Inbox payment states separate from merchant recognition.
- [x] New stable-ID mandates and PIN challenge binding. Existing null-ID mandates remain legacy-demo-only; no authority backfill.
- [x] Conversational selection corrections replace reviews and invalidate old approval; factual attention/status answers.
- [x] Home conversation in the primary page, existing voice recording/cleanup reused, adaptive energy threshold, actual payment cards.
- [x] Deadline-aware notification and UI controls; no background microphone or lock-screen financial details.
- [x] Lightweight committed-event logs, explicit unknown provider outcome, secret-free CI workflow.
- [x] Focused security, concurrency and browser verification; measured results below.
- [x] Manual release checklist and future integration boundaries documented below.

## Architecture and security decisions

`SpendingMandate.merchant_id` is nullable and added without assigning old rows to new identities. New permissions use the stable ID as the PIN challenge resource and include both ID and displayed name in challenge details. Active identity, immutable provider binding, unchanged identity name, PIN evidence, expiry and limits are revalidated at reservation and worker dispatch. An identity name change requires new approval. An old null-ID mandate is eligible only on the configured legacy single-demo merchant path with demo mode enabled. It never applies to versioned requests, even with the same name. Existing records remain queryable and revocable.

New batch snapshots also bind the merchant ID. Old unsubmitted reviews prepared before this schema should be refreshed and approved again; recorded journals, submitted attempts, receipts and historical authorization records are preserved.

`AttentionState` persists per-request dismissal/snooze separately from payment eligibility. Alerts may be disabled without hiding saved requests. Snooze is bounded by the real deadline; it never extends expiry or authorizes payment. Priorities are computed from server deadlines, not AI scores. Quiet hours affect background delivery, not payment memory. Already delivered device markers remain deduplicated through preference changes. Acknowledged delivery means the push endpoint accepted a send, not that the user saw it. Push may be delayed or unavailable; in-app memory is the fallback.

Home hosts the same assistant directly, without opening a second dialogue instance. The contextual dialog remains available on other screens. Explicit Talk/Voice starts recording; closing, mode changes and leaving Home stop it. Transcripts auto-submit by default, remain editable, and playback stays opt-in. Pause detection uses an adaptive energy threshold, not semantic VAD. Real device/noisy-room quality still needs manual testing. Never speak secrets: cloud transcription receives audio before the application can inspect its words. Recognized PIN/OTP text is blocked before model inference/history, but this is not a guarantee about transcription-provider exposure.

Corrections rebuild the exact snapshot, cancel the previous review and revoke its unconsumed approval. A changed, expired or externally paid selection requires a new review. Cards read backend payment and merchant fulfillment facts. Pending/unknown provider results keep reservations and remain Processing until reconciliation; no receipt is fabricated.

`providers.py` introduces structural protocols at the existing internal-payment and notification injection points, plus explicit unknown outcomes. Existing PayPal, funding, merchant and NVIDIA modules remain their respective service boundaries. There is no plugin registry or new rail. Every future funding adapter must pass the same authorization, journal and INR 100,000 posted-balance cap controls; every external checkout must preserve provider evidence and wallet separation.

Lifecycle JSON logs use an allowlist of correlation IDs/status/action fields, flush after commit, and discard rollback buffers. They never include PINs, approval tokens, credentials, private speech, descriptions or balances. They are diagnostics; the ledger/provider records remain settlement evidence. No external monitoring service was added.

## Verification record — 2026-11-10

- Full backend suite: **251 passed, 1 skipped** using the isolated PostgreSQL test project and existing dependency image. The skip is the optional offline Web Push adapter because that older image lacks `pywebpush`; normal requirements include it. After the final snapshot identity binding and ticket-specific question additions, the affected unit/HTTP plus complete PostgreSQL integration run passed **44 tests** (10 focused tests plus 34 PostgreSQL tests). These are separate measured runs, not a fabricated aggregate full-suite count.
- Expanded isolated PostgreSQL suite: **34 passed**, including additive migration/history preservation, wallet cap and reservation races, stable-ID concurrent allowance/replay, legacy-name collision isolation, stale batch approval rejection and uncertain settlement recovery.
- Focused initial V3 unit/HTTP run: **8 passed**; later additions cover ticket-specific questions and identity-bound batch snapshots.
- TypeScript/Vite build, Python compilation, Compose configuration and whitespace checks passed. CI YAML parses with read-only repository permissions. Actual GitHub Actions execution is **NOT EXECUTED** until the owner pushes/reviews the workflow.
- Existing browser suites passed: product 5 screens at 1440/1024/768/390 and 7 interaction groups; voice 7 fixtures; Guardian 9 fixtures; PayPal 7 fixtures; actual local V1 and V2 regression journeys.
- V3 A/B/C browser journey passed with an actual isolated FastAPI/SQLite API: merchant memory with alerts off; explicit synthetic speech auto-submission; correction/re-add; desktop/mobile exact review; PIN/journal settlement; separate fulfillment; real shortfall and separately PIN-authorized funding; fresh review; unknown outcome stays Processing until a real worker tick reconciles it. Only STT and the one-shot uncertainty adapter are synthetic. No financial response is mocked.
- Initial browser failures were test synchronization/copy assertions: old Home heading and an authenticated API call made before login completed. Both were corrected and rerun successfully.
- Screenshots: ignored `artifacts/v3-review/forgotten-checkout-390.png`, `home-conversation-390.png`, `exact-review-390.png`, `exact-review-1440.png`, `reconciled-receipt-390.png`; product screenshots also cover 1024/768. Captures were opened and inspected, with trust/status spacing and compact Home balance corrected from the rendered result.
- **NOT EXECUTED:** physical microphone, live NVIDIA inference, real OS notification delivery, PayPal Sandbox buyer approval/capture, physical mobile keyboard/safe-area hardware behavior, fresh production Docker image build, GitHub-hosted CI. Fixture success does not prove these integrations.

## Manual release checklist

From the repository root:

```powershell
docker compose up --build -d
docker compose ps
```

The normal startup applies additive migrations. Preserve all existing volumes. Provision merchant credentials only if those identities do not already exist:

```powershell
docker compose exec api python -m app.provision_merchants
```

Keep returned credentials server-side. Use the two terminal commands in `docs/MERCHANT_API.md` to open sample merchants on 8091/8092. Existing demo merchants/credentials need not be recreated or overwritten.

1. Save both local merchant checkouts, leave the pages, disable deadline alerts and reload Wallet-Voice. Both requests should remain visible. Dismiss/snooze/restore; confirm deadlines and payment eligibility never change.
2. Talk or type “What payments need my attention?” then “Pay the railway and food orders.” Try “Actually, just the railway,” “Add the food order,” “Remove the second payment” and “Cancel this review.” Approve only the final exact selection. Duplicate/ambiguous merchant matches must require clarification.
3. Observe exact recipient IDs, source, amount and deadlines. Check individual journal receipts, then merchant status polling. Confirm fulfillment separately. An expired/unpaid request must not be fulfilled.
4. Inspect permissions. A switch alone grants no authority. Create a stable-ID merchant permission via PIN; review amount/daily limit/expiry; revoke it. Legacy permissions must be labelled and cannot authorize a versioned identity.
5. In a secure browser, test microphone denial, recording stop/close/mode switch, transcript edits, normal pauses/noise, interruptions, opt-in speech playback, and session expiry. Never speak a PIN/OTP.
6. Test live NVIDIA, push and PayPal separately with explicit owner authorization. PayPal buyer approval cannot be replaced by the wallet PIN; internal wallet balances must not change for that external capture.

Repeat automated journeys from `frontend`:

```powershell
npm.cmd run build
node scripts/verify-product.mjs
node scripts/verify-voice.mjs
node scripts/verify-guardian.mjs
node scripts/verify-paypal.mjs
node scripts/verify-v1.mjs
node scripts/verify-v2.mjs
node scripts/verify-v3.mjs
```

Isolated integration suite (dedicated project, no development volume):

```powershell
docker compose -p walletvoice-v3-verification -f docker-compose.yml -f docker-compose.test.yml --profile test up --build --abort-on-container-exit --exit-code-from test test
```

## Future regulated partner and native boundaries

The application remains single-owner. A merchant currently submits requests only to that explicitly configured demo wallet; it cannot choose arbitrary customers. Real customer support requires authenticated user accounts, server-issued one-time checkout-link tokens bound to customer/merchant/order/amount/expiry, explicit customer acceptance and per-customer authorization, strict tenant isolation and audit/reconciliation ownership. Never infer a customer wallet from a phone number or merchant-supplied name.

Real stored value/bank funding requires an authorized regulated partner, jurisdiction-specific KYC/compliance and safeguarding, provider/customer consent, authenticated funding approvals, signed callbacks, reconciliation, disputes/refunds and actual settlement evidence. A wallet PIN cannot substitute for bank/provider authentication. No such partner or production bank/UPI transfer is implemented here.

Native notifications/background and system integrations require dedicated iOS/Android implementations and platform permissions. The web app cannot overlay unrelated applications or listen silently. Passkeys/WebAuthn require genuine challenge verification bound to the exact transaction; fake biometric approval is deliberately absent.

## Changed files

Backend: `models.py` and additive `20261112_guardian_v3.py` (identity/state persistence); `mandate_authority.py`, `agentic.py`, `services.py`, `execution.py`, `main.py` (identity-bound authority and legacy isolation); `reminders.py` (independent memory and alert state); `batch_voice.py`, `context.py`, `voice.py` (corrections and factual answers); `authorization.py`, `audit.py`, `payment_batches.py`, `merchants.py` (bound snapshots and committed lifecycle logging); `providers.py` (typed existing seams and uncertainty).

Frontend: `App.tsx` (primary Home, compact balance, recent actual activity and status/trust separation); `FloatingAssistant.tsx` (one inline/contextual conversation with cleanup); `VoiceAssistantPanel.tsx`, `ConversationPayments.tsx` (adaptive pause threshold, suggestions and real cards); `Workspace.tsx` (stable merchant selection and permission wording); `AttentionQueue.tsx` (independent reminder controls and snooze/dismiss/restore); `design.css` (focused layout, status spacing and safe-area updates).

Verification: `test_v3.py`, `test_v3_postgres.py`, legacy fixtures in `test_merchants_v2.py`/`test_merchants_v2_postgres.py`, `serve_v3_verification.py`, `verify-v3.mjs`, updated product fixtures, `.github/workflows/verify.yml`. README, testing/status documentation and demo script link this execution record. Generated screenshots, caches and credentials remain ignored.
