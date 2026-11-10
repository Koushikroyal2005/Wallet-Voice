# Implementation status

## Final V1–V3 quality pass — 11 November 2026

CI module invocation, coalesced deadline alerts, durable explicit snooze and current merchant-identity validation are implemented. Home uses shared backend attention data; dismissal is not cancellation. Revoked identities cannot start new internal dispatch or external capture, while reconciliation preserves confirmed provider evidence and historical receipts. No ledger rewrite, private credential edit, commit or push. See [FINAL_REVIEW.md](docs/FINAL_REVIEW.md) for the final measured matrix, file explanations, limitations and release gate; earlier dated results below are historical, not this pass's results.

Measured: full Linux/isolated-PostgreSQL run **288 passed, zero skipped/failed**; subsequent expanded migration/reminder/trust regression **18 passed** (overlapping, not added to 288). Production build, compilation, Compose validation and all seven browser suites passed; Voice now includes nine synthetic scenarios. Dedicated backend test image built successfully. Live providers, physical devices, full application rebuild/startup and GitHub-hosted CI remain unexecuted. Verdict: **READY WITH LIMITATIONS for the labelled simulated local demo**.

## Guardian conversation reliability — 2026-11-10

Grounded urgent-payment references, ambiguity/expiry checks, source memory, explanations, bounded assistant replay IDs and transaction-free model inference are implemented. AI prepares reviews only. Transcript review defaults on; spoken replies are opt-in. Closing/switching invalidates pending audio callbacks and stops microphone tracks. Provider labels distinguish NVIDIA inference, deterministic demo parsing, context resolution and speech fallback. Reviews preserve fractional rupees and require acknowledgement of unknown businesses.

Observed validation: **162 local tests passed, 16 PostgreSQL tests skipped locally**; the new assistant duplicate-turn PostgreSQL race ran separately in a fresh isolated schema and **passed (1)**. The other 15 integration tests were not rerun. Production frontend build, Python compilation, existing four-viewport browser checks and seven synthetic voice browser journeys passed. The original reset-based suite was not invoked; development data and private `.env` were untouched.

The 40-case deterministic dataset passed. Real configured NVIDIA Nemotron evaluation finished at **36/40 combined cases**, including **8/12 model-routed cases**, 24 context-resolver cases and 4 secret guards. Four live cases safely returned no preparation tool (decimal top-up, withdrawal, unfamiliar merchant and multiple train requests); they remain failed quality checks, not passed provider tests. Real microphone quality, live Whisper/Magpie audio, and real Sandbox payment approval/capture/webhooks were not verified in this phase. See `docs/VOICE_TESTING.md` for exact scope, commands, file changes and the manual device test plan.

## Repository-inspired conversation refinement — 2026-11-09

Applied interaction ideas to the existing assistant without adding a voice framework or changing payment execution: chat/voice mode changes preserve the component and unfinished input; short payment-source replies resolve against server-selected requests; corrections clear the selection; microphone input drives a visible meter; completed transcripts have an “I heard” label; recording requests echo cancellation/noise suppression; playback callbacks ignore interrupted generations; the microphone explicitly offers Interrupt while speaking. Closing/switching releases microphone resources. Financial review remains required.

Verified context/voice checks: 31 passed. Browser fixture journeys at four viewports and production build passed during this revision. No Docker or live-provider tests. Partial transcripts, spoken barge-in while TTS plays, semantic end-of-turn detection and continuous listening are not implemented; the interrupt action is a visible user control. No commits or pushes were made.

## Plain-language product refinement — 2026-11-08

- Compact Home assistant with direct Talk / Type controls, aligned actions and literal payment labels; original SVG companion replaces the generic bot and unverified online dot.
- Wallet uses explicit demo transfer labels and a short PayPal explanation with expandable bank-balance information. No personal connection is implied by merchant credentials.
- Auto-pay and Security are separate sections within the settings screen. Faster checkout and automatic incoming requests are explicitly distinguished; PIN controls are isolated. Setup and approval wording explains the business, limits and expiry.
- Assistant tips stop after interaction. Voice has an optional longer pause allowance, duplicate microphone-start protection, amount follow-up context and outcome-specific confirmation wording.
- Verified backend checkpoint: **64 passed, 13 PostgreSQL tests skipped**. Frontend production build and four-viewport fixture browser checks passed during refinement. No Docker, provider or real microphone tests were run.
- This is not the entire long-term roadmap: scheduled reminders, continuous listening/semantic interruption, cross-device preferences, new payment rails and real bank balance access remain unimplemented. Existing payment authorizations and financial rules were preserved.

## Floating conversational assistant — 2026-11-08

This checkpoint supersedes older verification counts below.

- Shared floating assistant: right-edge vertical dragging with saved position, single tap for chat, double tap for voice, held second tap and drag selection. Keyboard and right-click alternatives are available.
- Tips show for 10 seconds, rest for 5 seconds and can be dismissed. Attention animations respect reduced motion.
- Voice mode automatically records, ends a turn after detected silence, transcribes, submits and speaks. Chat stays quiet, with explicit Read aloud. Closing/switching releases microphone tracks and playback. This is turn-based voice, not continuous or streaming semantic turn detection.
- Backend list context resolves ordinal payment references, holds, source switching and cancellation. Financial actions still require existing review/authorization. Tool-specific argument validation rejects extra fields, invalid sources and coerced financial types; schemas explicitly describe paise units.
- Obvious numeric PIN/OTP disclosures are rejected before assistant storage/provider submission. This is a narrow guard, not comprehensive secret detection.
- Wallet now explains that PayPal checkout cannot supply the linked bank balance. Demo funding remains labeled simulated. No merchant balance is misrepresented as personal funds.

Validation: **61 backend tests passed, 13 PostgreSQL tests skipped**; frontend production build and Python compilation passed. Browser API-fixture checks passed at four viewport sizes, plus funding, draft creation, permission review, stale-preview clearing, dragging, double-click voice, second-click-hold chat, and microphone-denial fallback. Screenshots: `artifacts/product-review`.

Not executed: Docker/PostgreSQL, live NVIDIA, real microphone/silence accuracy, PayPal checkout/webhooks. Browser tests deny microphone access deliberately and do not establish real audio quality. Docker and credentials were untouched.

Still not implemented: arbitrary linked-bank balance access, continuous voice turn cycling, semantic interruption detection, phone-call/OS notification access, cross-device preference memory, or extra payment-provider integrations. Existing conversation history is reused; it is not unrestricted personal memory.

Research references: [PayPal balances](https://developer.paypal.com/api/transaction-search/v1/balances-get/) (scoped reporting, up to three-hour lag); [LiveKit turn handling](https://docs.livekit.io/agents/logic/turns/tuning/) and [repository](https://github.com/livekit/agents) (listening/completion/playback separation); [Google Pay reminders](https://support.google.com/pay/india/answer/11912288?hl=en-IN) and [PhonePe mandates](https://www.phonepe.com/terms-conditions/autopay/) (reminders are not payment authority); [Paytm UPI Lite](https://paytm.com/support/upi/how-to-pay-using-upi-lite-on-paytm) and [HSBC access](https://www.hsbc.bank.in/help/faqs/mobile-banking/) (rail-specific friction and authorization). No external framework code was copied and these services are not newly integrated.

## Current redesign and workflow revision — 2026-11-08

This section supersedes earlier completion claims for the latest source revision.

- Replaced the active UI with one design stylesheet and an assistant-first Home screen, payment review dialogs, recipient-backed drafts, wallet activity, merchant permission cards, numeric AutoPay rules, and a merchant checkout demonstration. The older stylesheets are no longer imported by the application entry point.
- Added a single-owner wallet sign-in gate using the wallet PIN, signed HttpOnly cookies, expiration, logout revocation, and invalidation on PIN change. This protects the existing demo wallet; it does **not** implement multiple customer accounts or production account recovery.
- Enabled sign-in in the local `.env`, generated a private session signing secret, and replaced the placeholder demo merchant key with a random key. Provider credentials were preserved. `.env.example` documents the new settings without a private secret.
- Fixed stale wallet activity/draft/permission views, recipient form races, invalid amount input, stale assistant previews, accessible modal focus, failed-payment messages, and persistent retry keys.
- Funding retries can reuse the same consumed approval only for the exact original operation. PIN changes revoke unused approvals. Draft authorization and reservation creation now commit together, and finalization updates draft state.
- Internal attempts cannot reuse a PayPal claim. PayPal creation retains external ownership after ambiguous errors; repeat calls use the same provider key. Capture no longer reports pending status as completed in the UI. Webhooks validate amounts and reject regressive approval/pending events after completion.
- Provider execution receives detached objects after the database transaction closes. Finalization locks and rechecks attempt state, rejects expired reservations, and releases merchant allowance on failure. Read-only payment listing preserves merchant accounting metadata.
- The worker now executes eligible AutoPay requests and resumes committed simulated attempts. Held requests remain excluded. Expiry is processed through settlement logic. Batch previews account for cumulative funds/daily limits and confirmation can be restricted to the displayed request IDs.
- Added five PostgreSQL race tests for duplicate batch confirmation, PIN approval consumption, merchant daily allowance, competing PayPal/internal claims, and mixed wallet operations. Database fixtures explicitly reject development database targets.

### Observed validation

- Full local suite at the intermediate checkpoint: **42 passed, 13 PostgreSQL tests skipped**.
- After adding wallet sign-in: targeted HTTP and product-flow suite: **19 passed**, including session protection, logout revocation, and PIN-change session invalidation.
- Fixture-based Chromium checks: **passed** for Home, Payments, Wallet and Permissions at 1440, 1024, 768 and 390 pixel widths, with no detected horizontal overflow or page errors. Exercised funding/activity refresh, saved-recipient drafts, permission review and stale-preview clearing. Screenshots are in `artifacts/product-review/`. This run preceded the final sign-in screen addition.
- Latest frontend production build and Python compilation: **passed**.
- Both Compose files parse as YAML. Docker CLI/config/runtime verification was **not executed**, as requested.
- Final full-suite/browser rerun: **blocked** by automatic approval review reporting that the workspace is out of credits. The final settings/security initialization race fixes and final sign-in screen therefore still need the final rerun. Earlier passing checkpoints are not a claim that this exact final revision passed every test.
- PostgreSQL, live NVIDIA, PayPal buyer approval/capture, and webhook delivery: **not executed in this revision**. Do not infer live-provider success from fixture tests.

### Remaining release boundaries

Multi-user account isolation, production recovery/device enrollment, real bank funding/withdrawals, PayPal recipient payouts, production merchant onboarding, and real IRCTC integration are not implemented. PayPal Checkout pays the configured Sandbox merchant; it must not be represented as arbitrary phone-number transfers. The current recipient flow explicitly uses simulated wallet funds.

See `docs/TESTING.md` for exact verification and startup commands. Docker and existing development volumes were not started, restarted, reset, or removed during this revision.

## Functional demo slice

- React/Vite dashboard with responsive payment inbox, voice/text panel, settings, ledger activity, loading and empty states.
- FastAPI wallet API, simulated bank account/top-up/withdrawal, append-only balanced journal entries and idempotent operations.
- Payment attempts and reservations: active reservations reduce available balance; successful demo payments consume a reservation and post the journal debit; failures release it.
- Demo merchant simulator, PostgreSQL-backed application events/SSE polling, server-side request/reservation expiry, deterministic urgency/policy trace, individual payment, hold and batch dry-run/confirm.
- Dashboard shows posted, reserved, and available balance values from the API; active reservations, batch previews/results, and unknown-merchant confirmation are present in the UI.
- An isolated Compose PostgreSQL test profile and integration-test suite are included. It ran successfully on 2026-11-08: 8 PostgreSQL tests passed against the ephemeral `aiwallet_test` database, including a complete pre-journal legacy-schema migration verification.
- Docker Compose services for PostgreSQL, API, worker, and web.
- Agentic wallet foundation completed on 2026-11-08: PostgreSQL-backed conversation memory, six-digit wallet-PIN challenges bound to an exact action/amount/resource, single-use approvals, durable payment drafts, recipient records, explicit user holds, scoped merchant spending mandates, and an idempotent merchant-checkout entry point. Bank/provider passwords are never collected; the current bank rail remains explicitly simulated.
- The React funding and voice-prepared funding flows now use the same backend PIN authorization contract. Explicitly held requests are excluded from batch and AutoPay evaluation until released.
- Voice assistant panel with typed-command fallback, browser recording, transcript review, explicit financial previews, confirmation buttons, and browser TTS fallback. FastAPI includes NVIDIA Riva Whisper upload conversion, Nemotron constrained tool calling, and Magpie synthesis adapters; neither an LLM nor a voice transcript can execute money movement.
- Phase 3 static and demo verification completed on 2026-11-08: Python compilation, 12 local tests (8 PostgreSQL-only tests skipped), frontend production build, Compose configuration, and the rebuilt isolated PostgreSQL Compose suite (8 passed).
- PayPal Sandbox structure: OAuth cache, Orders v2 adapter, explicit USD Sandbox representation, persistent provider orders/events, verified webhook path, and v6 SDK checkout panel. PayPal completion is externally funded and is deliberately ledger/reservation-free.
- Phase 4.5 connects voice payment preparation to an actual open Inbox request and the selected AI Wallet or PayPal source. The rebuilt isolated PostgreSQL suite passed 8 tests and the local unit suite passed 16 tests on 2026-11-08; NVIDIA and PayPal credentials were confirmed absent, so live smoke calls were not attempted.
- Phase 5 adds an explicit, idempotent demo initializer (`python -m app.demo`) and a credential-free backup demo path. It does not run automatically and its reset option deletes only labelled, unsettled seed requests.
- Product-hardening update (2026-11-08): the app now has distinct Home, Payments, Wallet, and Permissions workspaces; user-entered top-up/withdrawal amounts; durable P2P drafts; merchant spending permissions; held/history payment filters; an urgent-action surface; PIN change and lockout controls; and server-restored assistant conversations with a visible timeline.
- Financial authorization is now bound to immutable operation details, unknown-merchant confirmation cannot bypass balance or spending limits, mandate usage resets by calendar date, and merchant checkout requires a configured demo merchant key. PayPal order creation claims the request before the provider call so internal and external rails cannot both execute it.
- Local validation of this hardening update passed: 25 tests passed, 8 PostgreSQL-only tests skipped, Python compilation passed, and the frontend production build passed. Docker was intentionally not run or restarted for this update, so the new migration and concurrency behavior still require the isolated Compose command before deployment.

## Credential-gated / intentionally incomplete

- NVIDIA Riva Whisper, Nemotron tool-calling, and Magpie TTS adapters need the user's NVIDIA API key before live verification. Their default disabled state is intentional; live smoke status is reported as skipped until credentials are supplied.
- PayPal Orders, buyer approval SDK and signature-verified webhooks need Sandbox credentials and webhook ID before verification.
- PayPal live Sandbox OAuth, buyer approval/capture, and HTTPS webhook delivery remain credential-gated and unexecuted.
- Live verification update: Magpie TTS synthesis and PayPal Sandbox OAuth succeeded after enabling the configured credentials. Whisper/Nemotron and the buyer approval, capture, and webhook journey have not yet been run and are not claimed as verified.
- Production WebAuthn registration/assertion requires deployment HTTPS/RP configuration. `DEMO_AUTH_MODE` is plainly marked and is unsuitable for production.
- The current application is still a single demo-user system. Production identity, device enrollment/recovery, regulated bank rails, merchant onboarding, and a production-grade merchant authentication scheme remain outside this hackathon implementation. `DEMO_MERCHANT_API_KEY` is a local integration key, not a substitute for OAuth, mTLS, or signed production payment mandates.

The demo provider is the only route that can mark a simulated transfer/payment complete without a real provider confirmation. PostgreSQL row locking and dedicated concurrency verification are implemented; the isolated suite passed all 8 tests on 2026-11-08. The new PIN is an AI Wallet authorization control, not a PayPal or bank credential. P2P recipients and merchant mandates currently execute only through the labelled demo rail.
# V1 implementation — 10 November 2026

Implemented exact persisted batch reviews, immutable snapshots/hash, per-batch PIN approval, single-wallet approval, atomic reservations/idempotent settlement, individual results/receipts, aggregate ₹1 lakh wallet credit ceiling, automatic voice conversation, durable reminder queue/preferences and optional standards-based push. Current verification and manual limits are recorded in [docs/TESTING.md](docs/TESTING.md) and [docs/V1_IMPLEMENTATION.md](docs/V1_IMPLEMENTATION.md). No private credentials were read, no development database reset, and no commit/push performed for this task. Live provider/OS notification journeys are not claimed verified.
# V2 implementation update — 2026-11-10

Core authenticated merchant-to-wallet journey and V1.1 corrections implemented; no commit/push. See [V2 checklist, changed files and measured results](docs/V2_IMPLEMENTATION.md). Merchant provisioning, immutable checkout ingestion, PIN-bound batch settlement, polling and separate fulfillment are local simulations. Live NVIDIA, OS notifications and PayPal buyer journey were not exercised in this phase. Development Docker images require the owner's normal rebuild.

## V3 — 2026-11-10

Stable-ID merchant authority, independent saved-payment memory, non-financial snooze/dismiss/restore, inline Voice Home, conversational corrections, typed uncertainty handling, committed lifecycle logs and secret-free CI implemented. Existing journal/authorization/reservation/PayPal separation remains in place. Measured full backend run: 251 passed, 1 optional adapter skipped; expanded PostgreSQL run: 34 passed. Actual local A/B/C browser journey passed with synthetic STT/uncertainty only. Final affected checks and explicit unexecuted live-provider/physical-device/CI checks: [V3 execution record](docs/V3_IMPLEMENTATION.md). V3 changes remain uncommitted for owner review.
