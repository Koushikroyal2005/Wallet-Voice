# Desktop review and polish — 12 November 2026

Baseline: `712b591`, branch `main`. Changes are local only; no commit, push, deployment, private credential edits or development database operations were performed.

## Changes and file ownership

- `frontend/src/components/HomeOverview.tsx`, `App.tsx`, `Workspace.tsx`: urgent summary opens Pending Inbox and clears stale search. Home Add Money uses explicit parent state consumed by WalletView, replacing the timed custom-event handoff. Secure funding approval is unchanged.
- `ConsumerScreens.tsx`: one Batch Pay hero, a useful Split Bill tile instead of a duplicate batch action, and one simulated wallet summary separated from external source capability cards. No fabricated bank/card connectivity.
- `ActivityTimeline.tsx`: removed the repeated heading and wrapper card; preserved server data, filters, exact attempt records, receipt links and batch navigation.
- `Dialog.tsx`, `PaymentIntake.tsx`, `consumer.css`: scoped desktop intake layout with two-column fields, full-width URL, clear confirmation placement and the existing accessible scrolling native dialog. Fixed 1024px brand wrapping, desktop Pay action density, Activity search width and financial number hierarchy. Settings text, panels and permission controls can wrap instead of imposing a minimum width on narrow layouts.
- `frontend/scripts/verify-consumer.mjs`: desktop-only mode at 1024×900, 1280×800 and 1440×900; original six-size mode and strict overflow assertions retained. Added actual-backend tests for Home navigation, notification detail/dismissal, unchanged AutoPay rules and PIN-approved merchant permission revocation. Dismissal preserves saved requests; permissions do not debit funds.
- `verify-completion.mjs`, `verify-premium.mjs`: desktop-only mode with accurate viewport reporting; original mobile coverage retained.
- `NotificationCenter.tsx`: stable notice-ID attribute for testing actions independently of feed ordering. Notification delivery and state APIs are unchanged.
- `.github/workflows/verify.yml`: independent desktop job with consumer, completion and premium assistant suites. Completion/premium steps execute even if the consumer step fails, unless cancelled. Screenshots uploaded with `always()`. Existing frontend/mobile and backend jobs remain intact.

No dependencies, backend routes, financial policies, transaction authorization, journal behavior or provider behavior changed. Existing assistant lifecycle, compact voice answers and persistent conversation state were reused. No external design plugin was needed.

## Executed validation

- TypeScript + Vite production build: passed after the final source changes, 1,658 modules.
- Backend consumer/document/PayPal/voice tests: **54 passed** in 21.15 seconds.
- Backend merchant/domain/agentic/V3 tests: **39 passed** in 37.75 seconds, including mandate revocation and wallet transfer/policy behavior. No skips in these two selections.
- Desktop consumer suite: **passed all three requested sizes**, including real disposable FastAPI/SQLite batch settlement, wrong-PIN rejection, exact PDF records, saved requests, notification state, AutoPay rule preservation, merchant permission approval/revocation and PIN change/re-login.
- Final expanded six-size consumer suite: **passed at 360/390/430/768/1024/1440**, including the unchanged 360px Settings/AutoPay overflow assertion, stable-ID notification navigation/dismissal and the added AutoPay/permission regressions.
- Desktop completion suite: **nine journeys passed**, with three-size intake captures: unsafe URL rejection, non-executing unverified imports, hold/restore, QR fallback, synthetic QR cleanup, split preview/confirmation without debit, PDF catalog and notification preferences.
- Desktop premium assistant: **passed at 1024/1280/1440**, including transcript opt-in, compact answer, context across navigation, structured action cards, duplicate approval guard, microphone cleanup, error/retry and reduced motion. Responses are fixtures, not live model evidence.
- Existing `verify-product.mjs`: **passed five viewport sizes**, funding refresh, draft recipient, permission review, stale preview removal and assistant controls.
- Existing `verify-v3.mjs`: **passed** actual isolated exact batch/PIN/journal and recipient transfer journeys, correction/re-add, funding shortfall and reconciliation. STT is synthetic.
- Existing `verify-paypal.mjs`: **seven fixture journeys passed**: completed, denied, pending-to-denied, lost response, buyer cancellation, reload pending/capture and duplicate approval.
- JavaScript syntax checks and diff whitespace validation: passed.

An initial completion run failed after the Split tile changed its accessible name; an explicit label restored the existing action contract and the rerun passed. The new merchant permission test initially targeted the login PIN label rather than the existing secure approval label; corrected test locator and desktop rerun passed. A subsequent six-size run exposed a positional notification test locator; actions now target the immutable notice ID rather than the first row. An initial sandboxed backend test process made no progress and was interrupted; the equivalent normal-access runs passed above.

## Rendered visual inspection

Browsers captured all requested desktop sizes. Individual rendered PNGs were opened to inspect Home, Pay, Inbox, Activity, Accounts, Settings/AutoPay, notifications, intake, voice answer, exact batch review and completion. Inspection found and corrected brand wrapping, the Pay-grid cascade, repeated Activity headings, a constrained search box and incorrect balance emphasis.

Evidence remains in ignored local artifact folders:

- `artifacts/consumer-product/`: `home-1024.png`, `home-1280.png`, `pay-1280.png`, `pay-1440.png`, `inbox-1280.png`, `activity-1024.png`, `activity-1440.png`, `accounts-1280.png`, `accounts-1440.png`, `settings-1024.png`, `settings-autopay-&-permissions-1024.png`, `notifications-1280.png`, `notifications-1440.png`, plus all size variants and permission approval/revocation captures.
- `artifacts/prompt-completion/intake-1280.png` and 1024/1440 variants: scoped desktop checkout form.
- `artifacts/premium-assistant/voice-quick-answer-1280.png`, `exact-batch-review-1280.png`, `exact-batch-review-1440.png`, `recorded-fixture-success-1024.png`, `recorded-fixture-success-1440.png`: assistant and truthful fixture result presentation.

## Explicitly unexecuted / remaining external verification

- Current GitHub run `43093209291` for baseline `712b591` actually **failed** on `settings-autopay-&-permissions-360 overflow`; logs were inspected. The independent desktop job and local corrections have not run on GitHub because this task prohibits automatic push. Local success is not remote CI success or Linux visual certification.
- No live NVIDIA, physical microphone/camera, real Sandbox buyer capture or signature-verified webhook delivery was performed. Sandbox states above are fixtures. Hardware/assistive-technology verification remains manual.
- Isolated PostgreSQL integration suite and full backend suite were not rerun in this frontend-only task; this is not new evidence of PostgreSQL concurrency verification. No financial backend implementation was changed.
- No normal Docker restart/rebuild or deployment. Existing running containers will not automatically contain these local edits.
