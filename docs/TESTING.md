# Testing

## Guardian conversation evaluation

See [VOICE_TESTING.md](VOICE_TESTING.md) for the 40-case deterministic/live model dataset, measured failures, microphone lifecycle browser fixtures, isolated PostgreSQL replay test and real-device voice checklist. Live Nemotron inference, context-only follow-ups, demo parsing and synthetic browser audio are reported separately.

## Plain-language refinement checkpoint

Backend suite: **64 passed, 13 skipped**. Browser harness now uses Auto-pay & security, checks separation of PIN controls, and reviews the simplified checkout approval. Four viewports and existing financial fixture journeys passed. The assistant’s longer-pause option and physical microphone quality still require manual audio testing. Docker and live providers were not run.

## Floating assistant verification — 2026-11-08

Latest full local result: **61 passed, 13 skipped** (`python -m pytest -q`, backend). PostgreSQL tests were skipped, not passed. The initial sandbox run encountered temporary-directory permission errors; the approved local rerun passed. Frontend production build and Python compilation passed.

`node scripts/verify-product.mjs` from frontend passed with API fixtures across four viewport sizes. It now checks saved vertical dragging, no accidental opening during drag, double-click voice, second-click-hold drag to chat, and microphone-denial fallback. It also covers existing funding/draft/permission/stale-preview journeys. The sandbox could not find Chromium; the approved run used the installed browser. These are not live provider tests.

Manual real-audio checks still required: double-tap, speak, pause, confirm transcription auto-submits and response is audible; switch to chat and confirm silence; close during recording and verify the browser microphone indicator disappears; test silence/noise and slow speech; verify financial actions still stop at review/PIN/PayPal approval. The silence detector is a heuristic, not semantic understanding. Tap the microphone again for another voice turn.

No Docker was run. Start the app yourself with `docker compose up --build -d`. No new environment variables or credentials are required for these UI changes. Existing NVIDIA credentials are required for live audio/provider checks.

## Latest revision: run these checks

The latest production frontend build and Python compilation passed. Earlier in this revision the full local suite passed **42 tests**, with **13 PostgreSQL tests skipped**. The later targeted sign-in/HTTP/product suite passed **19 tests**. The final full rerun was blocked because automatic approval review reported that the workspace was out of credits. Consequently, do not treat the earlier results as final-revision PostgreSQL or browser verification.

From PowerShell, run the local suite:

```powershell
cd "E:\AI Wallet\backend"
python -m pytest -q
python -m compileall -q app tests alembic
cd "E:\AI Wallet\frontend"
npm.cmd run build
node scripts/verify-product.mjs
```

The browser script starts and stops its own Vite server on `127.0.0.1:5189`. It intercepts API requests with explicit fixtures and never uses the development database or payment providers. It captures the four main screens at desktop/tablet/mobile sizes and tests funding refresh, recipient draft creation, permission review, and stale assistant preview removal. Its latest completed run passed before the sign-in gate was added; the script now includes a fixture sign-in step, which needs a final rerun. Screenshots are saved in `artifacts/product-review/`.

The restored HTTP contracts use an isolated temporary SQLite database. On the reviewed Windows host, the sandbox prevented temporary-file/event-loop access; running the authorized tests outside that sandbox succeeded. The HTTP tests remain in the suite rather than being removed or reported as skipped.

### Start the application yourself

```powershell
cd "E:\AI Wallet"
docker compose config --quiet
docker compose up --build -d
docker compose ps
docker compose exec api python -m app.demo
```

The `migrate` service applies Alembic before API/worker startup. Open `http://localhost:8080`. The local `.env` now enables sign-in. Use your existing wallet PIN; an untouched demo wallet starts with `123456`. Changing `DEMO_WALLET_PIN` does not overwrite a PIN already stored in the database. Change it through Permissions after signing in.

`WALLET_SESSION_SECRET` was generated privately in the local `.env`. If creating a new `.env` from the example, set a private random value of at least 32 characters. `WALLET_COOKIE_SECURE=false` supports local HTTP; use `true` when the frontend itself is served over HTTPS. The sign-in gate protects one demo owner, not multiple user accounts. Logout invalidates existing owner sessions; changing the PIN also revokes unused transaction approvals.

Run the isolated PostgreSQL suite separately:

```powershell
docker compose -f docker-compose.yml -f docker-compose.test.yml --profile test up --build --abort-on-container-exit --exit-code-from test test
```

The current suite includes five additional race scenarios beyond the prior eight integration tests. It is **unexecuted for this revision**. It uses the isolated test database; never substitute the development database URL or run `down -v` as part of validation.

### Manual journeys after startup

1. Sign in, add demo funds with the PIN, and confirm that balance and recent activity update together. Withdraw an entered amount with a new PIN approval.
2. Create a recipient using a name and phone/email, select that record in a draft, save without moving money, then review/authorize once. Check that the completed draft loses its payment controls.
3. Add an Indian Railways permission with at least ₹1,250 per payment and an appropriate daily allowance. Review merchant, allowance and expiry on the PIN screen. Open Merchant demo and pay a sample ticket without leaving that page. Revoke permission and try another order; it must wait on hold for approval.
4. Ask for urgent payments, then “pay that one,” then “use PayPal instead.” Check each new preview and verify that editing input clears the previous confirmation action. “Cancel” must never execute a payment.
5. Test a fresh PayPal Sandbox request with a real Sandbox buyer. A pending capture must remain pending; verify completed capture, signed webhook delivery, duplicate delivery handling and unchanged internal wallet balance. This is not covered by browser fixtures.
6. Change the wallet PIN. The old session and unused approvals must become invalid; sign back in using the new PIN.

---

The entries below are historical verification checkpoints and do not replace the latest revision notes above.

Run `cd backend && pytest -q` for the fast unit suite. PostgreSQL-only concurrency tests are skipped unless `TEST_DATABASE_URL` is set.

Run the isolated PostgreSQL suite without touching the development volume:

```bash
docker compose -f docker-compose.yml -f docker-compose.test.yml --profile test up --build --abort-on-container-exit --exit-code-from test test
```

The test database uses a `tmpfs` data directory and separate `aiwallet_test` credentials. Before Alembic runs, `scripts/reset_test_database.py` resets only the guarded `aiwallet_test@test-db` schema so repeated runs cannot inherit a partially applied migration; it refuses any other database target. Verified on 2026-11-08: migrations completed and 8 PostgreSQL tests passed with exit code 0, covering concurrent withdrawals, duplicate idempotency keys, competing merchant reservations, concurrent daily-limit enforcement, duplicate payment attempts, reservation expiry, journal reconciliation, and legacy-schema migration.

## Agentic wallet authorization and context

`python -m pytest tests/test_agentic_wallet.py -q` covers transaction-bound, single-use PIN approval, invalid PIN rejection, backend-owned conversation history, explicit hold policy exclusion, and non-mutating drafts. The full local non-integration selection passed 23 tests on 2026-11-08. Python compilation and the frontend production build also passed. Live development smoke checks confirmed the Nginx frontend/API proxy, `/health`, PIN status, PIN challenge verification, recipients, drafts, and mandates against the migrated PostgreSQL database. No wallet funds were moved by the smoke check.

The demo PIN defaults to `123456` through `DEMO_WALLET_PIN`; override it in `.env` for a private local demo. Never use a real bank or PayPal password as this value.

The migration test creates a second random temporary PostgreSQL database, recreates the original pre-journal `wallets`, `ledger_entries`, `operations`, `payment_requests`, and `autopay_settings` tables, runs `alembic upgrade head` twice, verifies balanced journals and preserved non-financial data, then drops only that temporary database.

The fast suite remains separate: `python -m pytest -q tests` passes its SQLite-domain tests and skips PostgreSQL-marked tests unless `TEST_DATABASE_URL` is configured.

## Voice assistant

`python scripts/test_nvidia_connections.py` is a credential-gated smoke test. With the default empty NVIDIA key it reports `SKIPPED`; it never treats that as a passed live provider check. Run it after setting `NVIDIA_ENABLED=true` and `NVIDIA_API_KEY` to verify Magpie audio. The regular unit suite verifies demo intent parsing and that an assistant preparation preview does not mutate the ledger. Verified on 2026-11-08: the local suite passed 12 tests with 8 intentionally skipped PostgreSQL-only tests; the rebuilt isolated Compose suite passed 8 PostgreSQL tests.

## PayPal Sandbox

Ordinary tests mock/no-op external PayPal interaction and cover Decimal conversion, webhook deduplication, ledger separation, and voice selection of an actual payment request. `python scripts/test_paypal_connections.py` is credential-gated and performs OAuth only; it never captures an order. A real Sandbox buyer approval/capture and HTTPS webhook delivery remain unexecuted until credentials are configured. Verified on 2026-11-08: 16 local tests passed with 8 intentionally skipped PostgreSQL-only tests; rebuilt isolated Compose PostgreSQL suite passed 8 tests.

Live provider check on 2026-11-08: NVIDIA Magpie synthesis passed (a playable WAV was received); PayPal Sandbox OAuth passed. Whisper transcription, Nemotron tool calling, PayPal buyer approval/capture, and public HTTPS webhook delivery remain separate unexecuted checks.

## Product-hardening verification

On 2026-11-08, after the wallet/PIN, conversation, merchant-permission, and PayPal mutual-exclusion changes:

- `python -m pytest -q`: **25 passed, 8 skipped**. The skipped tests require `TEST_DATABASE_URL` and real PostgreSQL semantics.
- `python -m compileall app tests`: **passed**.
- `npm run build` in `frontend`: **passed**.
- Docker/Compose runtime verification: **not executed by design** because the requested work explicitly prohibited restarting Docker.
- Live NVIDIA/PayPal checks: **not executed in this validation pass**; the earlier provider status above remains authoritative.

After rebuilding, run the isolated PostgreSQL command at the top of this document. It must apply migration `20261108_product_hardening`, then return exit code 0 before the new database behavior is treated as PostgreSQL-verified. The normal development volume is not used by that command.

## Payment Guardian verification

See [PAYMENT_GUARDIAN.md](PAYMENT_GUARDIAN.md) for review behavior, changed files, actual test results and manual acceptance steps. Run the additional browser check from `frontend` with `node scripts/verify-guardian.mjs`.
# V1 verification — 10 November 2026

Run unit tests from `backend` with providers disabled and an isolated test configuration. The final local run with the Web Push dependency available recorded **197 passed, 20 skipped**; the skipped integration tests were executed separately against PostgreSQL (**20 passed**, including concurrent credits/cap, competing exact batches, duplicate confirmations, journal reconciliation and legacy migration). The integration fixtures now create fresh schemas/databases and retain them until the dedicated tmpfs service stops; no reset, TRUNCATE or DROP DATABASE command is used. `docker-compose.test.yml` runs migrations followed by pytest, without the old reset script. The PostgreSQL run used an existing dependency image with the current backend mounted read-only; a clean V1 Docker image rebuild remains a local release check.

Offline Web Push encryption/VAPID signing passed using ephemeral synthetic keys and a synthetic HTTP response; this verifies the adapter contract, not OS delivery. The dependency was installed only into ignored `artifacts/v1-python-deps` for verification. Without `pywebpush` installed, that one adapter test reports a skip. Python compilation, Compose configuration and `git diff --check` passed.

The production TypeScript/Vite build passed. Product fixture checks passed at 1440/1024/768/390, voice fixtures passed seven journeys, Guardian fixtures passed eight scenarios, PayPal fixtures passed seven journeys. `node scripts/verify-v1.mjs` passed a real FastAPI/isolated SQLite browser journey: login, exact reminder navigation, default voice auto-submit (synthetic STT), selection/exclusion/correction, PIN, duplicate click, two journal receipts, wallet reconciliation and untouched food request, desktop/mobile. Screenshots are generated under `artifacts/v1-review` and excluded from Git.

Real microphone quality, live NVIDIA inference/transcription/playback, PayPal buyer approval/capture/webhooks and OS Web Push delivery were **not executed** for V1. No private `.env` was read. Passing fixtures never establish provider success. See [V1 limits](V1_IMPLEMENTATION.md).

Commands (PowerShell, repository root):

```powershell
docker compose -p walletvoice-v1-tests -f docker-compose.yml -f docker-compose.test.yml --profile test up --build --abort-on-container-exit --exit-code-from test test
# Stop only this isolated test project afterwards; never use down -v on development.
docker compose -p walletvoice-v1-tests -f docker-compose.yml -f docker-compose.test.yml --profile test stop
cd frontend
npm.cmd run build
node scripts/verify-product.mjs
node scripts/verify-voice.mjs
node scripts/verify-guardian.mjs
node scripts/verify-paypal.mjs
node scripts/verify-v1.mjs
```

`verify-v1.mjs` deliberately starts a new SQLite file named `v1-browser-*` in a temporary folder and refuses any existing DB. It uses synthetic PIN/configuration, disables providers and never loads private `.env`. The fixture remains in the temp folder for inspection.
# V2 verification

See [the V2 execution record](V2_IMPLEMENTATION.md#verification-2026-11-10) for actual results and resolved harness failures. Run the new local browser journey from `frontend` with `node scripts/verify-v2.mjs`. It starts a fresh isolated SQLite backend, verifies an actual process restart, uses real merchant and financial HTTP routes, and never loads private `.env` credentials. It also opens both local merchant servers at test-only ports. This is not live NVIDIA/PayPal evidence.

The full backend test-image run also needs the public root `.env.example` mounted at `/.env.example` because an existing configuration test resolves that path from `/app/tests`. Do not mount private `.env`. Financial integration tests still require the dedicated `aiwallet_test@test-db` database and create fresh per-test schemas; never substitute a development URL.

## Final V1–V3 quality verification

Use [FINAL_REVIEW.md](FINAL_REVIEW.md) for this pass's measured results and failed/retried harness checks. `tests/test_final_review.py` exercises actual persisted reminder occurrences and revoked merchant identities; `tests/integration/test_final_review_postgres.py` reruns reminder/trust cases in fresh dedicated PostgreSQL schemas and adds concurrent identical snooze submissions. These use fake push delivery, not OS notifications. Voice browser verification additionally checks synthetic short pauses and patient-listening long silence.

Observed: the full Linux CI-equivalent passed **288 tests, zero failed/skipped**, including 50 isolated PostgreSQL integration cases. After expanding the legacy migration fixture, a separate overlapping PostgreSQL run passed **18 tests**, including both migration variants and final reminder/trust cases. All seven browser scripts, TypeScript/Vite build, compilation, Compose validation and diff whitespace checks passed. One upstream Starlette/httpx test-client deprecation warning remains. Live provider/device tests and GitHub-hosted execution were not run; no fixture result substitutes for that evidence.

The safe integration command remains:

```powershell
docker compose -p walletvoice-final-tests -f docker-compose.yml -f docker-compose.test.yml --profile test up --build --abort-on-container-exit --exit-code-from test test
# Stop only this isolated project afterwards. Never delete development volumes.
docker compose -p walletvoice-final-tests -f docker-compose.yml -f docker-compose.test.yml --profile test stop
```

The clean Linux CI equivalent runs from backend: `python -m compileall -q app scripts && python -m alembic upgrade head && python -m pytest -q`, with BOTH database URLs set to the dedicated `aiwallet_test@test-db`, providers disabled, login disabled only for that isolated test process, and a synthetic demo PIN. Do not point this at development. A full test-image run requires only the public `.env.example` at `/.env.example`; never mount private credentials. Normal Compose integration runs only `tests/integration` and does not need that extra configuration-test mount.

Frontend commands, run separately so failures are visible: `npm.cmd run build`, `node scripts/verify-product.mjs`, `node scripts/verify-guardian.mjs`, `node scripts/verify-voice.mjs`, `node scripts/verify-paypal.mjs`, `node scripts/verify-v1.mjs`, `node scripts/verify-v2.mjs`, `node scripts/verify-v3.mjs`.

## V3 verification (earlier pass)

See [the V3 execution record](V3_IMPLEMENTATION.md) for current results and limits. The full measured backend run passed 251 tests with one optional Web Push adapter skip. The expanded isolated PostgreSQL suite passed 34 tests. Final affected snapshot/identity checks and browser results are recorded in that execution record rather than silently combined into a fictitious single run.

From `frontend`, `node scripts/verify-v3.mjs` starts a fresh `v3-browser-*` database, disables credential loading/providers, and runs the forgotten-checkout, conversational-batch, and shortfall/uncertainty journeys against actual FastAPI financial endpoints. Only STT and one-shot adapter uncertainty are synthetic. Its test-only worker-tick endpoint exists solely in `backend/scripts/serve_v3_verification.py`, not production routes. Do not run that fixture server as the application.

The new GitHub Actions workflow uses disposable PostgreSQL and secret-free provider fixtures. YAML was parsed locally; GitHub-hosted execution remains unexecuted until an owner-approved push.
