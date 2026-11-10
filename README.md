# Wallet-Voice Guardian — V2

V2 adds authenticated local merchant checkouts: save railway and food requests, review both by voice, approve exact simulated-wallet amounts with one PIN, and let each merchant poll settlement before separately recording fulfillment. See [merchant API and two local examples](docs/MERCHANT_API.md) and [V2 checklist](docs/V2_IMPLEMENTATION.md). These are simulated merchants; no real railway booking, food delivery, bank or UPI integration is claimed.

Say “Pay the train and movie tickets, not the food order.” Wallet-Voice resolves stored requests, shows an exact review, checks wallet policies and requires one PIN for those exact simulated internal-wallet payments. It records each result and journal receipt separately. PayPal Sandbox continues to require its own buyer approval and provider-confirmed capture.

V1 adds automatic conversation after explicit microphone recording, editable transcripts, persistent exact batch reviews, transaction-bound PIN approval for single wallet payments, a ₹1,00,000 posted-wallet ceiling, a server-owned attention queue and configurable Web Push. See [implementation and limits](docs/V1_IMPLEMENTATION.md), [verification](docs/TESTING.md), and [demo](docs/DEMO_SCRIPT.md).

To use background reminders, configure `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` and `VAPID_SUBJECT` (a `mailto:` operator contact) in your private environment, rebuild, then choose **Enable background reminders**. HTTPS or localhost and a supported browser are required. Permission is requested only through that button. Without configuration, the durable in-app attention queue still works. Quiet hours use `APP_TIMEZONE` and can be edited in reminder preferences.

AI Wallet is a local-first fintech hackathon prototype with an append-only journal ledger, simulated bank transfers, payment reservations, deterministic payment policy, and background expiry processing.

> Demo mode is explicit. Bank movements and automatic payments are simulations; they are never represented as real bank transfers or unattended PayPal payments.

## Start with Docker

```bash
cp .env.example .env
# Before starting, set WALLET_SESSION_SECRET in your private .env (see below).
docker compose up --build
```

Fresh installs keep wallet sign-in enabled. Generate a session secret locally with `python -c "import secrets; print(secrets.token_urlsafe(48))"` and paste it into `WALLET_SESSION_SECRET` in your private `.env`. Do not share or commit it. Startup rejects a missing/short secret. Set your demo wallet PIN before initializing a new database; changing the environment does not replace an existing stored PIN.

Open `http://localhost:8080`; API docs are at `http://localhost:8000/docs`. Run `docker compose exec api python -m app.demo` to seed train, movie, electronics and food requests with an idempotent simulated opening top-up. Keep AutoPay off for the exact voice/PIN demonstration. Wallet funding and merchant settlement remain simulated. A user can prepare and review wallet payments without provider credentials using typed input; live microphone transcription requires NVIDIA configuration.

Before upgrading an existing volume, back it up with `docker compose exec db pg_dump -U aiwallet aiwallet > aiwallet-backup.sql`. Compose runs `alembic upgrade head` in the `migrate` service before API and worker startup. Legacy single-row ledger records are retained as `legacy_ledger_entries` and converted to balanced journal entries during the migration. If the legacy cached balance includes historical opening funds not represented by old rows, the migration creates one explicit `MIGRATION_OPENING_BALANCE` journal transaction to preserve the balance auditably.

## Local development

```bash
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload
cd frontend && npm install && npm run dev
cd backend && pytest -q
```

## Reproducible demo (Windows PowerShell)

```powershell
Copy-Item .env.example .env   # only when .env does not already exist
docker compose up --build -d
docker compose ps
docker compose exec api python -m app.demo
```

Open `http://localhost:8080` and API docs at `http://localhost:8000/docs`. The `migrate` service applies migrations before API startup. The demo seeder is idempotent: it creates a ₹10,000 simulated opening balance and Railway/CinemaPass/ElectroHub requests only when its labelled records are absent. To remove only pending, held, or expired labelled seed requests before recreating them, use `docker compose exec api python -m app.demo --reset`; it never deletes journals, wallet data, reservations, attempts, or PayPal records. Add `--autopay-enabled` only when demonstrating the policy-enabled state.

The application works with NVIDIA and PayPal disabled. Voice uses typed/demo parsing and browser speech fallback; PayPal remains unavailable rather than simulating a checkout. See [demo script](docs/DEMO_SCRIPT.md) and [PayPal Sandbox guide](docs/PAYPAL_LIVE_SANDBOX_TEST.md).

## Architecture

Integer paise are used throughout. `services.py` posts balanced debit/credit journal entries, calculates posted/reserved/available balance, enforces daily limits, creates reservations, and finalizes demo-provider results in separate transactions. PostgreSQL is used in Compose; SQLite is supported for focused unit tests only.

## Credentials and integrations

Copy `.env.example` and add NVIDIA and PayPal credentials only to the backend environment. The current prototype intentionally runs fallback text commands and demo payments with no credentials. NVIDIA Whisper/Nemotron/Magpie and PayPal Orders are reserved behind environment-gated adapters, so no secrets are shipped to the browser and no external call occurs in demo mode.

See [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) and the documents in [docs](docs).

PayPal Checkout is a separate Sandbox buyer-funded source: it never debits the simulated AI Wallet ledger. Setup, currency handling, and webhook instructions are in [PayPal setup](docs/PAYPAL_SETUP.md), [architecture](docs/PAYPAL_ARCHITECTURE.md), [webhooks](docs/PAYPAL_WEBHOOKS.md), and [payment sources](docs/PAYMENT_SOURCES.md). Real Sandbox approval/capture is credential-gated and has not been claimed as tested.

For isolated PostgreSQL concurrency tests, see [docs/TESTING.md](docs/TESTING.md). The test Compose profile uses a separate ephemeral database and never mounts `postgres_data`.
