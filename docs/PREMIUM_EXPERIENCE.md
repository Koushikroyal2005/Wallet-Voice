# Premium mobile and voice experience

This pass implements the supplied mobile/voice brief on the existing React/Vite/TypeScript and FastAPI application. Source changes are local; the normal Docker application was not rebuilt or deployed. Private `.env` credentials were not read or changed. No commit or push was performed.

## The original problem and the new lifecycle

`FloatingAssistant` previously chose a portal destination from `inlineTarget`. Home supplied `voice-home-session`, navigation changed that target, and an effect reset the mode. Opening voice inserted a large conversation into Home and hid the launcher. The assistant also unmounted on close, mixing microphone lifecycle with page layout.

There is now one controller, `useWalletAssistant`, mounted throughout the authenticated session, and one stable portal attached to `document.body`. Voice uses a compact dark response surface; chat uses a floating desktop panel or a mobile bottom sheet. Both read the same controller and backend conversation ID. Navigation and mode changes preserve messages, unfinished input and prepared reviews. Closing stops microphone tracks, recording/level intervals, audio, synthesis and pending callbacks, while keeping the conversation and review available to reopen. Session expiry unmounts the authenticated controller.

The orb's listening ring uses the actual Web Audio RMS measurement. Thinking uses a restrained rotation. Short read-only responses may collapse after 14 seconds when the user is not editing or inspecting expanded details. Errors, long content and action previews never collapse automatically. The last response remains in backend conversation history. Recording is explicit foreground capture; this is not continuous/background listening or a real-time streaming implementation.

Transcript review is the default for new users. Automatic submission requires disabling review explicitly in voice options; existing saved choices are respected. Speech playback is opt-in or a deliberate Read aloud action. Stop/interrupt, patient listening, retry IDs and provider labels remain available. Switching to voice originally also cleared a prepared preview inside `start()`; the new browser regression exposed this and the reset was removed.

## Screens and interactions

- Home: available simulated balance, Send/Add money/Activity shortcuts, concise deadline count, compact Talk/Type entry and one backend-authoritative saved-payment list. The earlier hero, next-payment card and duplicate request list are removed. Dismissal remains distinct from cancellation, and alerts-off requests remain visible.
- Payments: clear amount/merchant/status hierarchy; Open/Held/History filters; selectable requests with a server-created exact batch review; drafts and sample controls remain progressively disclosed. A review can now open directly by authoritative Attention ID even if the separate Inbox query has not loaded yet.
- Wallet: prominent balance, consistent funding controls, posted/reserved figures and scannable activity. Existing simulated funding, cap and bank-balance limitations remain explicit.
- Send/drafts: Home opens the existing recipient/amount/note form, with an explicit accessible Recipient label. Drafts retain their existing PIN-bound execution.
- Permissions/security: consistent neutral surfaces, grouped settings, merchant allowances, expiry and revocation, with the existing controls intact. Merchant examples remain separate demo tools.
- Guardian/PIN/PayPal: consistent sheets and amount typography. Checks and timeline are expandable; recipient, amount, source, deadline and required action stay visible. Individual batch amounts retain actual currencies. Receipt evidence and external pending/failed/refunded states remain unchanged.
- Assistant: ordinary taps and keyboard controls, a shared composer, corrected transcripts, balance cards, relevant payment cards, and persistent approvals. Body portals keep the underlying page in place. Mobile layout uses dynamic viewport units, safe areas and `visualViewport` updates for software-keyboard positioning. Reduced motion disables animation.

The visual system uses local system fonts, neutral white surfaces, charcoal/indigo typography and iridescence reserved for the orb. No stock image, Apple artwork, new UI framework, external font request or new dependency was introduced. Thirty-nine obsolete dock/fan/inline assistant CSS rules were removed. The original mascot remains as an inactive repository asset; it does not decorate the consumer screens.

## Small backend extensions

- `recipient_voice.py`: resolve an actual saved recipient by exact name or full handle, scoped to the owner, and create a simulated transfer draft. Unknown or duplicate names prompt clarification. The assistant returns saved destination details and the draft version; it never calls execution.
- `voice.py`: expose the preparation tool to the existing NVIDIA adapter, support deterministic “Send ₹500 to Rahul,” and validate model-extracted amount/recipient wording. Existing NVIDIA transcription/synthesis stay intact.
- `context.py`: handle a natural “Okay, pay it” follow-up by returning the same recipient draft for secure review. This does not execute it.
- `batch_voice.py`: understand “How much money will I have left?” and “Okay, pay it” against the existing immutable batch.

`RecipientTransferCard` uses the existing P2P challenge, PIN and execution endpoints. It passes the exact draft ID, amount, source and version, then opens the actual Guardian record. No new financial execution route, journal behavior, spending rule, authorization bypass, reservation logic or PayPal funding behavior was added.

## Files

New frontend modules:

- `src/hooks/useWalletAssistant.ts`: shared recording, transcription, playback, conversation and cancellation controller, extracted from the original component.
- `src/components/AssistantOrb.tsx`: accessible state/audio-driven control.
- `src/components/AssistantComposer.tsx`: shared input, microphone and send controls.
- `src/components/AssistantPreferences.tsx`: progressive voice/provider options.
- `src/components/AssistantResponseCard.tsx`: concise response and real balance presentation.
- `src/components/AssistantActionCard.tsx`: existing review and funding composition.
- `src/components/RecipientTransferCard.tsx`: saved-recipient review using existing PIN routes.
- `src/components/HomeOverview.tsx`: compact balance/actions/assistant entry.
- `src/premium.css`: responsive materials, tokens and component styling.
- `scripts/verify-premium.mjs`: four-size assistant lifecycle and screenshot suite.

Modified frontend:

- `App.tsx`: simpler Home, exact Inbox selection, stable assistant mount and Attention ID review.
- `FloatingAssistant.tsx`: persistent overlay, ordinary controls, focus restoration, collapse and viewport handling.
- `VoiceAssistantPanel.tsx`: presentation only; shared chat/voice views and contextual cards.
- `AttentionQueue.tsx`: one saved-payment list with readable deadlines and actual currency.
- `Workspace.tsx`: Home funding/draft entry and accessible recipient selection; existing financial routes preserved.
- `PaymentGuardian.tsx`, `PaymentBatchReview.tsx`: progressive policy/identity details and accurate currency.
- `lib/formatting.ts`: currency-aware request formatting.
- `design.css`: system font and obsolete assistant rule removal.
- `main.tsx`, `index.html`: active styles and viewport/safe-area setup.
- `verify-product.mjs`: five viewport sizes, Send/PIN captures and new overlay interaction assertions.
- `verify-v1.mjs`, `verify-v3.mjs`: explicit synthetic auto-submit opt-in and updated real-backend journeys.
- `verify-guardian.mjs`, `verify-paypal.mjs`: current accessible review/disclosure interactions; behavioral assertions retained.

Backend files are the four modules listed above, `tests/test_premium_conversation.py` and `tests/integration/test_premium_conversation_postgres.py`. `IMPLEMENTATION_STATUS.md` links to this execution record.

## Verification and visual evidence

Measured: affected backend voice/context/model-adapter tests **100 passed**. Dedicated isolated PostgreSQL suite **62 passed, zero skipped/failed**, including saved-recipient preparation, exact P2P PIN authorization, duplicate reconciliation and existing ledger/concurrency/migration regressions. It used only `aiwallet_test@test-db` in `walletvoice-premium-verification`, with disabled live providers and source mounted read-only. That dedicated service was stopped after verification. One upstream Starlette/httpx test-client deprecation warning remains.

The production build, Python compilation, nine voice browser scenarios, nine Guardian scenarios, seven PayPal fixture scenarios, five-size Product verification, the V1 and V2 actual FastAPI/SQLite journeys, and the new four-size assistant suite passed. The final V3 journey also passed the new saved-recipient UI: it resolved Rahul from actual saved data, displayed his exact destination, required the existing P2P PIN challenge, recorded the actual simulated payment, and reconciled the resulting wallet balance. The same journey verified Inbox selection, voice/chat/navigation continuity, correction/re-add, two journal receipts, separate fulfillment and pending worker reconciliation. Fixtures are not live NVIDIA, PayPal capture or actual microphone evidence.

No tests were skipped in the two backend runs above. Initial iterations failed on a cleared preview during a mode switch, a late-loading Inbox row, an embedded select's accessible name, natural comma punctuation, a too-short synthetic token and old selectors for newly expandable details. The implementation and relevant assertions were corrected; final affected suites passed. An early command selected a nonexistent test file and collected no tests; it is not included as verification. The successful frontend build and browser scripts are the release evidence, rather than those initial failures.

Screenshots:

- `artifacts/premium-before`: preserved prior desktop/mobile Home captures.
- `artifacts/premium-review`: unlock, Home, Inbox, Wallet, settings, Send, PIN and Guardian at 390×844, 430×932, 768×1024, 1024×900 and 1440×900; interaction captures include chat and microphone denial.
- `artifacts/premium-assistant`: idle, listening, thinking, quick balance, shared chat, exact review, payment preview, PIN, fixture success, microphone failure and a simulated keyboard viewport at 390/430/768/1440.
- `artifacts/v3-review`: actual isolated-backend batch review, worker reconciliation and recipient receipt evidence.

Screenshots were opened and inspected. A subsequent visual correction fixed idle-orb visibility, active navigation contrast, mobile density and the size of read-only voice answers. Captures disable entrance animations so they show settled material rather than a partially transparent transition frame. Assertions verify no page/panel horizontal overflow, no Home displacement, preserved conversation IDs, cleanup, approval/error persistence and reduced motion.

## Limits and manual checks

Physical iPhone/Android keyboard behavior, hardware microphone quality, live NVIDIA calls, real OS push and real PayPal Sandbox buyer/capture/webhook delivery were **NOT EXECUTED**. The keyboard check resizes a browser viewport; it does not substitute for a physical keyboard/device test. Contrast/readability were visually inspected, not certified by an independent accessibility audit.

Deterministic recipient transfer wording expects an exact saved name or full phone/email. It does not discover arbitrary phone numbers, access another app, read OTPs, book tickets or retrieve personal bank balances. Merchant apps and internal money remain simulated. PayPal Sandbox remains external and separately buyer-approved. Native device context access, continuous listening and real-time streaming were not implemented.

To show these source changes in the normal local Docker app after review, run `docker compose up --build -d` from the repository root. No volume deletion/reset is needed. Browser verification starts isolated Vite/FastAPI fixtures without changing the normal application.
