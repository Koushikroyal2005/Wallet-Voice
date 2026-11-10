# Final V1–V3 review — 11 November 2026

Baseline: `a83a59d103f3a9a80862350026a3896e38102138`. Changes are local, not committed or pushed. This is a focused prototype quality pass, not security certification or production banking readiness.

**Verdict: READY WITH LIMITATIONS for the explicitly labelled local, simulated hackathon journey.** Not approved as a real-money production wallet, and not evidence of live NVIDIA, OS push or PayPal buyer success.

## Final four-fix follow-up — 11 November 2026

All four requested fixes are implemented in the existing uncommitted working tree: module-based CI migrations and V3 browser CI; one initial urgent reminder and durable explicit snooze; identity revalidation through review/PIN/reservation; and shared backend-authoritative Home attention with dismissal/restore while preserving Inbox and alert-independent memory.

This follow-up additionally rejects an explicitly versioned checkout whose identity binding is missing, rather than treating it as legacy. The historical single-demo path is preserved; its shared `merchant_checkout` category alone is not used to infer versioned identity. New parameterized regressions cover missing identity, missing versioned binding and authenticated-name collision. Reminder test time is fixed so the quiet-hours regression does not depend on the hour verification runs.

Files additionally changed in this follow-up: `backend/app/merchant_trust.py`, `backend/tests/test_final_review.py`, `backend/tests/integration/test_final_review_postgres.py`, and this document. The complete retained four-fix implementation file list appears below.

Measured this follow-up: focused backend regressions **72 passed**; final identity plus legacy-checkout regressions **22 passed** (overlapping, not added together); TypeScript/Vite build passed; V3 actual FastAPI/isolated-SQLite journey passed, including alerts-off memory, Home dismissal/restore and retained Inbox request; existing product browser verification passed at 1440/1024/768/390. An initial targeted command named a nonexistent test and collected no tests; the corrected selection passed. The complete isolated PostgreSQL suite **passed 54 tests, zero failed/skipped, exit code 0, 153.75 seconds**, following successful compilation and `python -m alembic upgrade head` with `PYTHONPATH` unset. This ran only against `aiwallet_test@test-db` in the dedicated `walletvoice-final-verification` project, with disabled live providers and current source mounted read-only. One upstream Starlette/httpx test-client deprecation warning remains. The older 288/18 results below remain explicitly historical evidence from the preceding pass, not results of this follow-up.

GitHub-hosted CI and live-provider/real-money checks are **NOT EXECUTED**. No commit, push, development reset, volume deletion or private credential change was performed.

## Issues fixed

- **P0 CI imports:** execute Alembic through `python -m alembic` from backend. Preserve the frontend job and add the existing real-backend V3 browser journey with Python dependencies. CI uses disposable PostgreSQL and disabled live providers. GitHub-hosted status is **NOT EXECUTED** until an owner-approved push.
- **P1 duplicate alerts:** schedule one automatic stage appropriate to the current deadline. Cancel obsolete upcoming jobs, coalesce notifications already delivered within the urgent window, and allow a later meaningful escalation with a five-minute minimum separation. Successful device deliveries remain recorded across retries. Older SENT rows without a delivery timestamp conservatively suppress automatic escalation; no historical delivery time is invented.
- **P1 explicit snooze:** create a separate durable `SNOOZE:<request_id>` occurrence even after an automatic notification was SENT. Repeated keys cannot create another occurrence, including after delivery or supersession. A new action cancels pending predecessors. Reminders are bounded to at least 30 seconds before the original deadline and rejected when too late. Payment memory, automatic alerts and explicit reminders remain separate; quiet hours, opt-out, dismissal and terminal states still govern delivery.
- **P1 merchant trust:** derive current authority from the persisted merchant-order relationship and authenticated identity, not display-name matching or a historical verified flag. Recheck at policy/review, PIN snapshot validation, claim/reservation and simulated dispatch. Identity changes invalidate unsubmitted snapshots. Revocation releases a queued internal reservation instead of dispatching it. Legacy single-demo requests remain isolated; completed journals and receipts remain historical records.
- **P1 external capture:** block creation/new capture for invalid merchant identity. Read-only reconciliation still records real provider evidence if capture already happened. No external debit/reservation is added to the simulated wallet.
- **P2 Home consistency:** shared backend attention query drives urgency, next request and review summary. Dismiss removes Home prominence but not the Inbox; restore updates all Home surfaces. Explicit loading/error states avoid presenting missing attention data as an empty account. Reminder actions have synchronous duplicate-submission protection and transport retry keys.
- **P3 review clarity:** current invalid merchant authority is explained plainly; recognition/PIN cannot override it. Historical receipts do not imply current merchant approval. Keep the existing visual system, accessible dialogs, explicit Talk/Type controls and reduced-motion support.

## Financial/security review scope

Preserved React/Vite/TypeScript, FastAPI/SQLAlchemy/PostgreSQL, append-only double-entry journal, reservations, idempotency and transaction-bound PIN authorization. No new dependency, payment rail, background microphone, autonomous AI payment authority or unrelated rewrite was introduced.

Existing tests exercise server-owned IDs/amounts; exact batch selection, amount, recipient, source and expiry binding; stale/consumed approval rejection; competing claims and duplicate confirmation; balance/daily limits and the ₹1,00,000 posted-wallet cap; balanced journals; failed/uncertain results; PayPal separation and evidence validation; merchant credential ownership; mandate revocation/expiry; cancellation/refund/fulfillment separation; and allowlisted lifecycle logs/secret guards. This does not prove every possible attack is excluded. In-flight operations cannot retroactively be undone by revocation; authoritative settlement evidence must remain accurate.

The additive migration `20261113_final_quality` adds nullable reminder delivery time. Existing unpaid reviews created before identity snapshot fields were added must be prepared again. No financial history is removed, no reset is performed, and no development volume is used for verification.

## Changed files and purpose

- `.github/workflows/verify.yml`: backend module invocation and V3 browser CI.
- `backend/app/merchant_trust.py`: centralized current merchant facts.
- `backend/app/services.py`: fail-closed policy/reservation checks.
- `backend/app/payment_batches.py`: identity-bound snapshot validation and current trust information.
- `backend/app/execution.py`: pre-dispatch revalidation/release.
- `backend/app/paypal.py`: invalid-identity creation/capture guard with evidence reconciliation.
- `backend/app/main.py`: truthful payment/review verification fields.
- `backend/app/models.py`, `backend/alembic/versions/20261113_final_quality.py`: additive delivery-time persistence.
- `backend/app/reminders.py`: stage coalescing and durable explicit snooze.
- `backend/tests/test_final_review.py`, `backend/tests/integration/test_final_review_postgres.py`: focused reminder, revocation, receipt preservation and PostgreSQL concurrent snooze regressions.
- `backend/tests/test_v1.py`, `backend/tests/test_v3.py`, `backend/tests/test_merchants_v2.py`: update the intentional one-alert policy and assert distinct explicit occurrence semantics.
- `backend/tests/integration/test_legacy_migration.py`: verify both pre-journal upgrade and an old reminder table without the new column; preserve prior delivery history across repeated migration.
- `frontend/src/App.tsx`, `frontend/src/components/AttentionQueue.tsx`: backend-authoritative Home, action protection, errors and plain-language snooze.
- `frontend/src/components/PaymentBatchReview.tsx`, `frontend/src/components/PaymentGuardian.tsx`: current trust and historical receipt explanations.
- `frontend/scripts/verify-product.mjs`, `frontend/scripts/verify-paypal.mjs`: authoritative attention fixtures.
- `frontend/scripts/verify-v3.mjs`: actual-backend Home dismiss/restore and Inbox persistence checks.
- `frontend/scripts/verify-voice.mjs`: synthetic short/long pause coverage.
- `README.md`, `docs/TESTING.md`, `IMPLEMENTATION_STATUS.md`, this file: current evidence and limitations.

## Measured verification

The first sandbox pytest invocation failed because its temporary directory was inaccessible; rerunning with normal temporary-directory access resolved that environment blocker. One initial Linux collection attempt exposed an import-order error in the new regression harness, now corrected. One old reminder assertion and the PayPal fixture attention response were corrected and rerun. The extended migration fixture initially used an unbound JSON literal and was corrected to a bound parameter. These initial failures are retained here rather than misrepresented as passes.

- **PASSED:** full Linux Python 3.12 backend/CI equivalent: **288 passed, 0 failed, 0 skipped**, exit code 0, 353.17 seconds. Both URLs pointed only to `aiwallet_test@test-db` in `walletvoice-final-verification`; the existing development database/volume was not used. This includes the then-current **50 PostgreSQL integration tests**, unit/HTTP/domain/voice/context tests and offline Web Push adapter. `PYTHONPATH` was explicitly unset; module Alembic and compilation passed before pytest. Latest code was mounted read-only into the freshly built dependency image; only public `.env.example` was mounted for configuration tests. One Starlette/httpx test-client deprecation warning remains.
- **PASSED:** separate final local merchant-trust/PayPal-focused run: **52 passed**, synthetic providers only.
- **PASSED:** TypeScript/Vite production build; Python compilation; Compose configuration validation; `git diff --check` (line-ending notices only).
- **PASSED:** Product browser fixtures: four widths (1440/1024/768/390), five screens and seven interactions. Guardian: nine scenarios. Voice: **nine** synthetic scenarios, including short-pause continuity and patient-listening silence stop. PayPal: seven mocked SDK/API journeys. Actual FastAPI/isolated-SQLite V1, V2 and expanded V3 journeys passed.
- **SKIPPED:** none in the successful full Linux run. The earlier Windows baseline lacked PostgreSQL configuration and the optional Web Push package (35 skipped); these were not counted as passes and were subsequently exercised inside Linux. That earlier run also had one now-corrected assertion failure and is not the final result.
- **NOT EXECUTED:** live/provider/device checks listed below, full application Docker build/startup, and GitHub-hosted CI.

The legacy migration fixture was subsequently expanded to cover an existing pre-column reminder table as well as the original pre-journal schema. The final separate PostgreSQL migration/reminder/trust rerun **passed 18 tests, zero failed/skipped**, exit code 0, 23.69 seconds. This includes both repeated migration variants and concurrent identical explicit-reminder submissions. It overlaps the complete run and is not added to 288 as if it were one non-overlapping full-suite run. The final expanded matrix contains 51 PostgreSQL integration cases; 50 were in the complete run, with both migration variants verified separately afterwards.

Already observed: TypeScript/Vite production build passed; Product browser fixtures passed at 1440/1024/768/390 (five screens, seven interactions); Guardian nine scenarios passed; PayPal seven SDK/API fixture scenarios passed; original Voice seven scenarios passed; V1, V2 and expanded V3 actual FastAPI/isolated-SQLite journeys passed. V2 includes a real backend process restart and both local merchant pages. V3 includes corrected selection, two PIN-bound journal receipts, duplicate click protection, dismissal/restore, shortfall funding, uncertain outcome and worker reconciliation. Only speech and the uncertainty adapter are synthetic. The dedicated backend test-image Docker build passed; this is not a full application image rebuild.

Screenshots captured in ignored `artifacts/product-review` and `artifacts/v3-review`; desktop Home and mobile exact PIN review were opened and inspected, not merely generated. Automated overflow assertions cover all four widths. Physical keyboard/OS virtual-keyboard behavior, a screen-reader audit and measured contrast audit remain manual; no accessibility certification is claimed.

## Required manual verification — individually NOT EXECUTED

- Physical microphone on a real device, short and long natural pauses and denied permission.
- Live NVIDIA transcription/tool calling/TTS in this pass.
- Actual OS Web Push delivery (fake send/encryption tests are not delivery evidence).
- Real PayPal Sandbox buyer approval, capture and signature-verified webhook delivery in this pass.
- Physical mobile devices, keyboard safe areas and assistive technology.
- Fresh full application Docker image build/startup; only the dedicated backend test image was built here.
- GitHub-hosted CI; the local Linux equivalent is separate evidence.

## Remaining risks and release boundary

- **P1 live integration evidence:** provider journeys require operator credentials, Sandbox buyer and device permissions; never claim these passed from fixtures/OAuth alone.
- **P2 delivery guarantees:** Web Push is best-effort. A process crash after provider acceptance but before database commit can still redeliver; per-device persisted deduplication is not distributed exactly-once delivery. Stable push tags help replacement, not guaranteed OS deduplication.
- **P2 packaging:** Python dependency ranges are not locked; a clean build can resolve newer packages. Dependency deprecation warnings are not silently suppressed.
- **P2 licensing:** no root LICENSE/COPYING file found. Owner must choose/confirm repository license; no license was selected or added.
- Prototype remains single-owner, simulated money, not a regulated multi-user wallet. Production requires regulated partners, customer identity, authenticated customer-to-checkout linking and compliance.

## Reproducible few-minute demonstration

Run `node scripts/verify-v3.mjs` from frontend for isolated deterministic evidence without credentials. For a presentation use the two authenticated local merchant examples described in `MERCHANT_API.md` and `DEMO_SCRIPT.md`; never reset development data. Save railway and food checkouts, leave merchant pages, show remembered requests with alerts off, type “Pay the railway and food orders,” then “Actually, just the railway,” then “Add the food order.” Review the exact requests and simulated balance, enter the PIN only in secure review, show individual journal receipts, then poll both merchants: payment confirmed, fulfillment unconfirmed. Mark simulated fulfillment separately. Show an insufficient-balance/expired request or the test-only uncertain-outcome journey; never label pending as paid.

All wallet funds, demo bank top-ups/withdrawals and local merchant examples are simulated. PayPal is Sandbox and separately buyer-approved. No real PhonePe, UPI, IRCTC, Swiggy, bank, ticket-booking or delivery integration exists. Payment confirmation is not fulfillment. The web app cannot silently listen or overlay arbitrary mobile apps.
