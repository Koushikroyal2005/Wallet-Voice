# Master prompt coverage and second-pass implementation

Current completion: [FINAL_COMPLETION.md](FINAL_COMPLETION.md). The earlier partial Unicode/form/Settings/history/visual items below are historical and were closed in the final repository pass. Provider capabilities explicitly unavailable in the prototype and unperformed physical/live checks remain separate limitations.

The entire supplied 3,000+ line brief was reread in sequential chunks. This checklist maps its 31 parts to actual source, rather than treating a successful build as proof that every requested feature exists. It supplements, and supersedes the remaining-scope list in, `CONSUMER_PRODUCT.md`.

Status meanings: **implemented** means runnable local code; **verified** means an executed check is recorded below; **conditional/future** means the brief explicitly requires real provider/account/device support that this prototype does not possess; **partial** is not a claim of completion.

## Owner-requested final cross-check and publication

The owner subsequently requested publication to the current branch (`main`). Earlier statements below about uncommitted/unpushed work describe the implementation checkpoint, not a prohibition on this explicitly authorized publication. All 31 sections remain accounted for; partial/provider/device limitations are deliberately not relabelled as completed. The final small UI correction replaces document type/status/trust enums with readable labels while preserving API values and evidence boundaries. Its browser regression asserts that uploaded files are explicitly unverified, not proof of payment. The production build was rerun successfully. No normal Docker deployment or private credential change is included. Publication outcome is reported separately after Git returns.

Final label regression: `verify-completion.mjs` passed all nine journeys and six intake viewports using the existing host Chromium. The initial sandbox attempt could not launch because its browser cache was absent; the successful retry required no dependency installation. Physical camera and live providers were disabled and are not verified by this run.

## 1. Execution and truthfulness

Implemented locally on the existing dirty worktree, preserving the first redesign. No new dependency, provider, stack replacement, commit, push or normal application deployment. No credential edits, real external payments, development reset or volume deletion. Test PostgreSQL uses a separate named project and tmpfs storage. Demo funds, expected bills, uploaded invoices, authenticated merchant requests and PayPal Sandbox remain different concepts.

## 2. Existing implementation preservation

Reused `services`, `authorization`, `payment_batches`, `batch_routes`, `agentic`, `context`, `paypal`, `merchant_trust`, `reminders` and the persistent assistant. The journal, reservations, immutable reviews, financial idempotency, PIN expiry/lockout and merchant revocation checks are not replaced. Existing backend and browser suites were rerun. New models are additive and non-executing.

## 3. Navigation

Implemented four primary tabs, bell, account entry, secondary money/account navigation and a persistent orb. Settings is not a bottom tab. The prototype is explicitly a demo, with Merchant Demo kept separate. Desktop grouping is adapted to the existing state-based shell rather than adding a routing framework. Additional diagnostics and a separate production account system are not invented.

## 4–5. Design system and references

Semantic tokens, light/dark/system preferences, local system fonts, indigo/navy surfaces, restrained iridescent orb, tabular financial values and reduced-motion CSS are implemented. Existing Lucide/Motion dependencies are retained. No third-party component code was copied or framework installed. Browser screenshots, not source inspection alone, informed contrast, tablet navigation, document wrapping and PIN guidance corrections. Exact aesthetic certification and physical-device performance testing remain unexecuted.

## 6. Home

Available simulated balance, four quick actions, compact Talk/Type, one authoritative attention queue and server-derived planning insights are implemented. New `PlanningInsight` presents urgent IDs, possible duplicates, currency-aware expected bills and a wallet funding gap, explicitly not model predictions. Review suggested batch only selects real urgent request IDs; it does not approve them. Upcoming bill entry is actionable through the planning card. Optional hide-balance control is not implemented.

## 7. Pay

Send, Request, Batch Pay, saved-recipient search, manual checkout entry, HTTPS link paste, QR/paste fallback and Split a bill are implemented. Clicking a saved recipient preselects that exact ID in the existing draft flow. Recipient transfers still require the existing exact PIN challenge. Bank/card/UPI operations are not falsely represented as connected capabilities.

## 8. Smart Inbox

Implemented All/Pending/Held/Expiring/Expired filtering, search, urgency-first sorting, exact checkboxes, sticky currency-grouped selection and clear-selection. Backend policy expiry codes supplement conservative browser deadline display; execution always revalidates server-side. Imported checkouts appear separately and cannot be selected as executable payments. Hold/restore/dismiss and explicit in-app reminders are implemented for imports. Existing connected-payment attention/snooze actions remain intact.

## 9. Batch engine

Manual and voice use the same existing immutable server-owned batch. Exclusions, corrections, stale approval invalidation, independent merchant acknowledgement, exact PIN authorization, reservations, duplicate confirmation, limits and worker reconciliation remain. Results show actual statuses, references and currency-aware totals, including successfully journaled amounts. Mixed-source universal authorization is deliberately not implemented: wallet batches remain wallet-only, and PayPal uses its own buyer approval. No new payment rail or permission expansion.

## 10. Results

Recorded wallet success, partial, failed, expired, cancelled and processing views are implemented. Success styling is driven by backend state, not a timer. Batch totals distinguish submitted values from successfully journaled values; references and record downloads are present. Generic preview notices are neutral, not green settlement claims. Native focus moves to changed outcomes; uncertain outcomes remain pending. New partial/pending browser responses are labelled fixtures, while the complete wallet journey uses a real isolated journal.

## 11. Documents

Implemented searchable payment/statement/upload/refund catalog, record previews, summary printing, supported-device summary sharing, structured record PDFs and consolidated currency/status-aware statements. Uploaded PDF invoices/bills are size/type/header/end-marker validated, stored privately, and served as attachments with CSP sandbox and nosniff. They are explicitly unverified and never payment evidence. Search reads actual records; missing invoices are not invented.

Partial/conditional: authenticated merchant-issued invoice ingestion is not connected; uploads do not assert issuer verification. The existing lightweight PDF renderer uses WinAnsi and is not full international-font PDF typography. Malware scanning and legal tax-invoice generation are not implemented or claimed. No raw uploaded PDF is executed or rendered inline in the application.

## 12. Notifications

Implemented All/Needs Review/AI Updates, server-owned unread count, persistent read/dismiss state, linked payment/batch/section actions, deadline insights, due in-app bill/import reminders, payment notices and PIN-change security notices. Payment/AI/planning categories and push lock-screen privacy are persisted. Security-critical notices survive category opt-outs. Existing quiet hours, consent, push-device dedupe and payment status checks remain. Desktop uses a 440px anchored modal popover; mobile uses the existing responsive sheet.

Partial: notification history is a bounded projection of existing events plus current attention, not an infinite independent event archive. Background Web Push still covers connected saved-payment deadlines; new planning reminders are explicitly in-app only. Comprehensive security-event taxonomy, OS delivery and physical lock-screen behavior are not claimed verified. Marking a notice read does not cancel or dismiss its payment.

## 13. Accounts & funding eligibility

Implemented actual posted/reserved/available wallet values, configured capability cards and server read-only eligibility per existing payment. Wallet decisions reuse existing policy. PayPal eligibility checks configuration, currency representation, request state and merchant authority and requires buyer approval; its configured demo FX is explicitly not a live quote. Unsupported PayPal preparation is disabled in the picker, with reasons. Bank/card methods show unavailable balances and no connected operations. Real tokenized linking/removal requires a provider and is conditional, not simulated.

## 14. Send, Request and split

Existing Send uses exact saved recipients and PIN authorization. Voice supports `Send 500 to Rahul for dinner`, `Pay Priya 250`, saved-recipient listing and natural cancellation without guessing a destination. Request Money has explicit save/replay/cancel and text sharing; voice can prefill a non-executing review.

New split preview resolves actual saved participants, includes the owner's share, allocates indivisible paise deterministically, hashes the exact snapshot and requires explicit confirmation before atomically creating individual requests. Replays cannot duplicate the requests. Outstanding request amounts and zero provider-confirmed repayments are shown honestly. There is no public buyer repayment rail; requests are not marked received without evidence. Public hosted collection links remain conditional; the brief's supported text-summary path works.

## 15. Bills & subscriptions

Implemented manual expected expenses, renewal dates, recurring tracking flag, archive, explicit in-app reminders and weekly/monthly/yearly expected-date advancement with month-end/leap-year handling. A stale expected date cannot advance twice on replay. Advances never mark a bill paid or authorize a debit. Voice queries filter actual saved records for this week/month and subscriptions, and can open the exact renewal reminder review. Expected spending is derived from saved amounts.

Partial/conditional: no utility account/biller connection, autonomous renewal debit, provider-confirmed last bill payment or automatic catch-up scheduler is fabricated. Recurrence is explicit expected-date planning, not an independent automatic-charge engine. Existing AutoPay/mandates remain the only automatic internal payment authority.

## 16. Share and intake

Implemented separate relational `PaymentIntakeRecord`, source type/URL, claimed merchant, exact user-reviewed amount/currency, deadline, dedupe digest, trust/status, hold/dismiss/restore and reminder time. Manual/link/QR/share intake never creates a verified executable `PaymentRequest`. URLs are never fetched, crawled or treated as authorization. Supported PWA share-target metadata opens a review form after unlock; it never silently saves or pays. Other-app context/email/native notification imports remain conditional platform integrations.

## 17. QR and links

Implemented explicit camera permission, native `BarcodeDetector` capability detection, HTTPS QR decoding, paste alternative, stop/close cleanup, unsafe-URL rejection and explicit external handoff only after acknowledgement. A decoded QR does not verify a payee. Unsupported native detection gets an honest paste fallback. Synthetic browser tests prove decoding/track cleanup, not physical camera compatibility. UPI/card URI execution and arbitrary cross-app payment completion are not supported.

## 18. Assistant

Persistent voice/chat controller, compact HUD, actual audio-amplitude orb, transcription review, patient listening, retry/dedupe, opt-in speech and safe collapse remain. New tools list recipients, search real documents, derive insights, filter bills by time, prepare split/request reviews and open exact saved-bill reminders. Non-payment resources use `resource_id`, never a fake payment FK. AI still cannot authorize money movement. Live NVIDIA and physical microphone quality are unexecuted here; deterministic/context modes remain labelled.

Partial: general free-form creation/editing of every bill setting, multilingual conversation, semantic cross-document extraction and unrestricted Siri-like device context are not implemented. Unsupported external actions stay unsupported rather than becoming invented successes.

## 19. Settings

Implemented account overview and links, existing PIN/security/AutoPay/merchant-permission controls, notification consent/quiet hours/categories/privacy, shared voice preferences, persisted appearance and privacy/help explanations. PIN mismatch/six-digit messages, field clearing and session revocation remain functional. Verified phone/email and real profile editing are conditional on a real account system. Server-history deletion/account deletion/export are not claimed available; the privacy page says so.

## 20. Forms

Existing native accessible `Dialog`, shared field/button classes, validation/error/loading/busy behavior and the secure PIN flow are reused. Added real intake, QR review, split review, upload and reminder controls instead of decorative buttons. Broad Pydantic errors now display their safe message text rather than only a generic failure. New bill/import/request forms perform their stated actions. The Add Recipient form remains the original inline fieldset, not a stacked dialog. Physical software-keyboard behavior and an independent screen-reader audit remain manual verification.

## 21. Activity

New backend-owned chronological timeline groups wallet batches and avoids counting their attempts twice, separates standalone external/internal attempts, and treats topups/withdrawals as simulated wallet movements. Filters support All/Sent/Received/Bills/Batch/Pending/Failed and search real references/dates/descriptions. Requested money and tracked bills are not misrepresented as received payments. Document/shared-request and detailed-history sections are progressively disclosed. Processing records link back to existing reconciliation-capable reviews.

## 22–23. Architecture, migrations and safety

Existing capture→review→authorize→execute→reconcile engine remains. New intake/split/upload/planning services cannot execute payments. Additive migration `20261115_product_completion` adds planning fields/tables without changing financial history; existing journal/reservation/authorization tables are not reset. User ownership is explicit for new records, but this is still the existing single-owner prototype, not production multi-tenant authentication. No raw card/CVV, provider secrets in the browser, model-supplied verification, universal external PIN or real FX quote is introduced.

## 24. Component architecture

Extracted intake, split, documents, planning settings/insights and Activity timeline into dedicated typed components. React Query owns server data; local state owns forms; localStorage holds only preferences/conversation identifiers. Existing CSS token aliases integrate the new semantic tokens. No framework swap or blanket rewrite. The pre-existing large `App`/`Workspace` are not comprehensively rewritten; further decomposition is an incremental maintainability improvement, not a delivered production architecture claim.

## 25–26. Responsive behavior and motion

Six requested viewports are covered by existing consumer verification and new intake captures. Native dialogs, focus/escape, labelled controls, safe areas, wrapping, reduced motion and keyboard-aware assistant behavior remain. Rendered screenshots were inspected and corrected. Confirmation is never synthesized by animation. Physical Android/iOS, hardware performance, real keyboards, browser-native QR availability and full WCAG certification remain unexecuted.

## 27. Tests

Executed suites and latest numbers are in the results addendum below. Existing financial tests and assertions were preserved. Test-only SQLite files, PostgreSQL tmpfs schemas and synthetic browser device/provider frames are separate from development data and real provider evidence. CI was not pushed or remotely executed. One local optional Web Push dependency remains missing; isolated PostgreSQL skips are not counted as local passes.

## 28–31. Execution and final acceptance

The second pass is actual implementation, not another proposal or CSS-only pass. P0 financial/approval behavior is preserved and verified. The missing local P1/P2 workflows above are implemented with explicit trust/capability boundaries. The optional future integrations and partial items above remain honest limitations. Do not interpret this checklist as claiming every production feature or every physical-device/provider acceptance test passed.

The 30 acceptance criteria map to: build/regression evidence (1–2); shell/bell/batch entry (3–6); shared batch/PIN/journal/receipts (7–14); shared forms/settings/security (15–18); persistent assistant/context (19–21); capability labels (22,26); browser captures and correction (23–25); no real payment, secret disclosure or data destruction (27–29). Criterion 30, overall perceived product coherence, requires owner/judge judgment rather than an automated pass assertion.

## Changed files in this pass

- Backend: `models.py`, `main.py`, `product.py`, `reminders.py`, `voice.py`, `context.py`, `agentic.py`; new `intake.py`, `splits.py`, `document_store.py`, `planning.py`, `capabilities.py`; additive migration `20261115_product_completion.py`; unit/PostgreSQL `test_prompt_completion` files.
- Frontend: `App.tsx`, `ConsumerScreens.tsx`, `Workspace.tsx`, `Dialog.tsx`, `NotificationCenter.tsx`, `PaymentGuardian.tsx`, `PaymentBatchReview.tsx`, `AssistantActionCard.tsx`, `AssistantResponseCard.tsx`, `useWalletAssistant.ts`, `lib/api.ts`, `consumer.css`; new `PaymentIntake.tsx`, `SplitMoney.tsx`, `DocumentCenter.tsx`, `PlanningControls.tsx`, `ActivityTimeline.tsx`; PWA `manifest.webmanifest` and `sw.js`; new `verify-completion.mjs`.
- Documentation: this checklist, current pointers in implementation/testing/final-review reports. No private `.env` edit, dependency installation or push.

## Results addendum

Initial extended local backend run: 278 passed / 92 skipped. Subsequent run: 281 passed / 95 skipped (94 isolated PostgreSQL cases plus one optional local Web Push dependency). Targeted consumer/voice tests: 65 passed. Initial expanded PostgreSQL runs passed 91, then 94 tests, with one upstream Starlette/httpx deprecation warning. Final rerun results are appended after completion, not inferred from these earlier counts.

The original product (five viewports), consumer (six viewports), V3 actual-backend payment/PIN/journal, voice 9, Guardian 9 and PayPal fixture 7 journeys passed during this pass. New completion browser journey passed unsafe-link rejection, non-executable import, hold/restore, QR fallback, synthetic camera cleanup, split preview/confirmation with unchanged balance and PDF import/catalog/preview. It captured all six intake sizes. Physical cameras and providers were not used.

Final full local run: **282 passed / 96 skipped**, 218.36 seconds. Of the skips, 95 require isolated PostgreSQL and one requires the optional local Web Push adapter dependency. Earlier counts above are not added together or represented as independent distinct passing cases. Final TypeScript/Vite production build passed; final consumer six-viewport run passed after the chronological timeline change. Python compilation, quiet Compose validation and diff-whitespace checks were also executed; their final results are recorded at handoff.

Final isolated PostgreSQL run: **95 passed, zero skipped/failed**, 307.83 seconds, after successful `python -m alembic upgrade head`. One upstream Starlette/httpx test-client deprecation warning remains. Project `walletvoice-completion-verification` uses only the dedicated `aiwallet_test@test-db` tmpfs database and current source mounted read-only; no development database or volume is used. Python compilation, quiet Compose configuration and diff checks passed. No GitHub CI or live-provider result is inferred from these local runs.

Final four-size premium assistant lifecycle run also passed after all additions. The dedicated PostgreSQL test container was stopped after verification; normal application containers and volumes were not restarted or removed. All source changes remain uncommitted/unpushed. Physical microphone/camera/keyboard, OS share-target/Web Push delivery, live NVIDIA and PayPal buyer/capture/webhook journeys remain unexecuted.

Screenshots: `artifacts/prompt-completion` (intake sizes, unverified review, exact split, request result, document import/preview, QR fallback/decode and notification preferences); existing `artifacts/consumer-product`, `premium-review`, `premium-assistant`, `v3-review` retain the main application and payment journeys. The completion suite was rerun after a busy-guard wait correction and a scoped Notifications selector; product verification caught an inline recipient-fieldset regression and passed after restoration. Rendered document wrapping was corrected after image inspection.
