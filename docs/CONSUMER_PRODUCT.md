# Consumer product redesign — implementation record

## Second-pass update

The full master brief has now been reread and audited in [MASTER_PROMPT_COVERAGE.md](MASTER_PROMPT_COVERAGE.md). That report supersedes the initial remaining-scope list below: safe link/manual/QR intake, split requests, PDF import/search/preview, planning reminders and renewal advancement, notification categories/privacy/security notices, source eligibility, chronological Activity, recipient search and additional non-executing voice tools have since been implemented. Initial results below remain historical evidence, not final totals.

Reference source: `bd7e16d`. This implementation remains local and uncommitted. No push, deployment, production payment, normal application rebuild, private credential edit, database reset or development-volume deletion was performed.

## Delivered

- Four primary destinations: Home, Pay, Inbox, Activity. Desktop money/account navigation is separate. A compact top bar provides the notification bell and account/Settings entry. Mobile and tablet use the same four-tab bottom navigation.
- Home has a server balance, explicit simulated label, Send/Request/Add money/Batch Pay shortcuts, one backend-authoritative attention list, and compact Talk/Type controls. Dismissal remains different from cancellation. Alerts-off requests remain saved.
- Pay features manual/voice batch entry, saved recipients, the existing Send/draft flow and manual bill tracking. Unsupported QR/bank/card operations are not represented as functional buttons.
- Inbox preserves exact selection and independent merchant review; adds a sticky selection/amount/clear bar. Totals are grouped by currency. Open, Held and Expired filters separate outstanding work from Activity.
- Exact batch review retains existing immutable server snapshots, unknown-merchant acknowledgement, PIN authorization, duplicate-submit guard, polling and reconciliation. Its timeline and completed/failed/pending summary use actual backend states. Outcome changes focus the result heading and return the dialog to the top. Partial/pending states do not receive success animation.
- Activity displays batch history, individual record links, wallet operations, separate PayPal Sandbox order records and simulated money requests. Search and category filtering are provided without combining external and internal balances.
- Downloadable structured payment-record PDFs and currency-aware batch statements use backend evidence. Previewing a request cannot generate a completed-payment receipt. Failed/pending records explicitly are not proof of successful settlement. These are Wallet-Voice records, not merchant tax invoices.
- Notification center provides All, Needs Review and AI Updates, an authoritative unread count, server-persisted read/dismiss actions and relevant record links. Existing attention and allowlisted application events are reused. Deadline insights are explicitly backend-derived, not represented as NVIDIA inference. Dismissing a notice does not dismiss the saved request.
- Settings groups account links, security/AutoPay, notification consent/quiet hours/Web Push, shared voice preferences, appearance and privacy/help. PIN changes, spending permissions and automatic-payment controls continue using their existing routes. Light/Dark/System preferences are persisted; reduced motion remains respected.
- Accounts & Cards shows actual configured capabilities, explicitly missing bank/card connections and unavailable external balances. PayPal Sandbox remains separately buyer-approved; no transfers between PayPal and the simulated wallet were introduced.
- Request Money saves an idempotent simulated request with payer, exact amount, note, cancellation and copyable summary. It neither contacts the payer nor changes a balance or claims receipt of money.
- Bills/subscriptions manually track expected INR expenses and renewal dates. Archiving is supported. These are estimates, not connected biller accounts, automatic charges, renewal schedules or scheduled reminders.
- Existing persistent assistant remains mounted across navigation. New read-only tools return actual tracked bills, money requests and batch records. Existing exact voice/manual batch preparation and authorization are reused. Voice preferences in Settings update the same controller; PINs/OTPs are not routed to a new AI interface.

## Architecture and files

Backend additions:

- `app/models.py`: `NotificationReadState`, `MoneyRequest`, `TrackedBill`. Owner-scoped relational planning/read-state records, separate from financial tables.
- `alembic/versions/20261114_consumer_product.py`: additive table creation. Existing journals, requests, authorizations, reservations and provider records are untouched. Downgrade requires a separate retention plan.
- `app/product.py`: `/api/product` notification/read-state, request/cancel, bill/archive, batch-history and source-capability routes. Event payloads are not blindly exposed. The application remains an explicitly single-owner demo.
- `app/documents.py`: authenticated read-only document endpoints and a small paginated text-PDF renderer using built-in PDF Helvetica. No dependency, remote fetch or screenshot-to-PDF conversion.
- `app/main.py`: register the two routers, inside the existing wallet-session middleware.
- `app/voice.py`: three narrowly scoped read-only tools and deterministic equivalents. Existing NVIDIA adapters and financial execution are unchanged.
- `scripts/serve_v3_verification.py`: optional test-server port to run independent disposable browser environments.
- `tests/test_consumer_product.py`, `tests/integration/test_consumer_product_postgres.py`: planning, isolation, replay, read-state, document evidence, actual PIN settlement and read-only conversation regressions.

Frontend additions:

- `components/ConsumerScreens.tsx`: Pay, Activity, Accounts, manual requests, manual bills and grouped Settings, reusing existing dialogs and controls.
- `components/NotificationCenter.tsx`: shared feed query, three sections, read/dismiss and record navigation.
- `components/VoiceSettings.tsx`: persisted voice preferences shared with the existing controller.
- `tokens.css`: centralized light/dark/system semantic colors. Existing premium token aliases point to them.
- `consumer.css`: scoped consumer shell/forms/result/notification styles, tablet/mobile navigation and restrained recorded-success animation; no new component framework.
- `scripts/navigation.mjs`, `scripts/verify-consumer.mjs`: public-path navigation helper and real isolated-backend consumer journey at six sizes.

Frontend modifications:

- `App.tsx`: shell destinations, bell/account controls, request entry, selected-payment summary and server-state views. Existing Guardian, funding, SSE and assistant paths are reused.
- `HomeOverview.tsx`: four quick actions and Activity link.
- `AttentionQueue.tsx`: one attention list; notification preferences are available separately in Settings.
- `PaymentBatchReview.tsx`: truthful result timeline/summary, currency grouping, record downloads and accessible outcome focus.
- `PaymentGuardian.tsx`: download the existing authoritative payment record.
- `Workspace.tsx`: explicit mismatch/six-digit guidance in the existing Change PIN form; PIN authorization behavior is unchanged.
- `AssistantPreferences.tsx`, `hooks/useWalletAssistant.ts`: persisted read-aloud preference and shared preference updates, without remounting conversation state.
- `main.tsx`, `premium.css`: import semantic tokens/consumer styles and initialize saved appearance.
- `verify-product.mjs`, `verify-premium.mjs`, `verify-v3.mjs`: adapt navigation selectors to the consumer shell; preserve financial and assistant assertions. The continuity test navigates through the reachable Pay primary tab rather than opening Settings underneath an expanded assistant.

No new dependencies, payment providers, financial policies or autonomous execution paths were introduced.

Documentation changes: this execution record, `IMPLEMENTATION_STATUS.md`, `docs/TESTING.md`, and a latest-evidence pointer in `docs/FINAL_REVIEW.md`.

## Measured verification

- Final local full backend run: `python -m pytest -q -rs --tb=short` — **259 passed, 73 skipped**, 159.05 seconds. Of these skips, 72 require the separately run PostgreSQL environment; one optional Web Push adapter test lacks `pywebpush` in the local Windows interpreter. Skips are not passes.
- Final isolated full PostgreSQL suite: migrations succeeded, **72 passed, zero skipped/failed**, 215.69 seconds, with one upstream Starlette/httpx test-client deprecation warning. The initial full run passed 71 tests; the final run includes the additional read-only conversation case. Existing migration/concurrency/ledger tests are included, using independent fresh schemas.
- Targeted final consumer/voice/evaluation run: **55 passed**, 18.05 seconds. Python compilation passed.
- TypeScript/Vite production builds passed. Existing product browser verification passed across five sizes. Voice **9**, Guardian **9** and PayPal SDK fixture **7** journeys passed. Existing V3 actual SQLite/backend/PIN/journal journey and four-size premium assistant lifecycle suite passed.
- New consumer browser journey passed across **360×800, 390×844, 430×932, 768×1024, 1024×900, 1440×900**. It verifies real isolated login, notification persistence, non-spending requests/bills, shared voice preferences, PIN mismatch/change/re-login, typed deterministic batch preparation, wrong-PIN session revocation/re-login, fresh exact review, actual simulated settlement from INR 10,000 to INR 8,150, two actual journal references and actual PDF responses. Partial/pending presentation uses explicitly labelled browser fixtures, not real provider evidence.
- Compose configuration passed `config --quiet`, avoiding credential output. `git diff --check` passed with only line-ending notices.

PostgreSQL uses project `walletvoice-consumer-verification`, `docker-compose.test.yml` test-db, tmpfs storage and a current-source read-only mount into the existing test dependency image. Test commands use `python -m alembic upgrade head` followed by `pytest -p no:cacheprovider -q tests/integration`. They never use the development database. No reset or volume-removal command is used.

Initial failures were distinguished from final results: sandbox temp-directory permissions required an approved isolated-test rerun; one broad combobox selector was scoped to its dialog; the continuity test needed the new primary navigation; the new actual-backend journey was corrected to respect existing session revocation after a wrong PIN; the theme select received an explicit accessible label. An expanded browser rerun hit a startup load timeout and passed after using DOM readiness with a larger startup deadline. These failures were rerun, not hidden by removing assertions.

## Rendered evidence and visual correction

Reproduction commands (from `backend`): `python -m pytest -q -rs --tb=short` and `python -m compileall -q app tests alembic`. From `frontend`: `npm.cmd run build`, `node scripts/verify-consumer.mjs`, `node scripts/verify-product.mjs`, `node scripts/verify-premium.mjs`, `node scripts/verify-voice.mjs`, `node scripts/verify-guardian.mjs`, `node scripts/verify-paypal.mjs`, and `node scripts/verify-v3.mjs`. PostgreSQL requires the isolated environment described above; a local skipped run is not equivalent.

Existing before captures remain in `artifacts/premium-before`. Current captures are in `artifacts/consumer-product`: Home/Pay/Inbox/Activity/Accounts/notifications/Settings at all six sizes, exact review, actual batch success, explicit partial/pending fixtures, request summary, Activity documents, voice preferences, manual bill form/saved bill, PIN mismatch and dark Settings. Existing suites also retain funding, Send, PIN, permissions, Guardian and assistant-state captures in `artifacts/premium-review`, `artifacts/premium-assistant` and `artifacts/v3-review`.

Screenshots were opened and inspected. Subsequent corrections improved tablet bottom navigation, pale sidebar text, dark-mode active/notice contrast and success-result scroll/focus. Horizontal overflow is checked for pages and dialogs. This is rendered browser QA, not certification on physical mobile devices.

## Initial remaining scope — historical, superseded by the second-pass report

- P2 QR scanning, imported-payment intake, public payment links/PWA share target and split-bill requests are not implemented.
- Bills are manual tracking only; automatic recurrence, renewal reminders and biller payment execution are not implemented. Existing saved-checkout reminders remain separate and unchanged.
- Money requests are local demo records with text sharing, not public buyer checkout links or verified incoming transfers.
- Mixed-source batch orchestration and universal external PIN approval are not implemented. PayPal is single-order Sandbox checkout with its own approval flow.
- Real bank/card funding, account aggregation, verified personal bank balances, invoice upload and merchant tax invoices are not implemented.
- Documents use built-in WinAnsi Helvetica; non-Latin text is replaced in PDF output. Full international PDF typography, dedicated document search and invoice ingestion remain future work.
- AI can list new planning records; voice creation/editing of bills or money requests and semantic document search are not implemented.
- Notification history is a bounded projection of existing events/current attention with persistent read-state, not an unlimited independent event archive or comprehensive security-notice system.
- Proper multi-user accounts/ownership, server-history deletion and production compliance are outside this single-owner prototype.
- Physical microphones/keyboards, live NVIDIA inference, real Web Push delivery, live PayPal buyer approval/capture/webhook delivery, and GitHub CI were **not executed**. Configured providers and fixture responses are not proof of live integration.

To see the changes in the ordinary Docker app after owner review/backup, run `docker compose up --build -d` from the repository root. This uses the existing migration service. No volume deletion or reset is required. This command was not run against the normal application in this task.
