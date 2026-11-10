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
