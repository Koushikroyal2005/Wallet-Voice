# Wallet-Voice agent instructions

These rules apply throughout this repository.

## Architecture

- Keep React, Vite and TypeScript; keep FastAPI, SQLAlchemy and PostgreSQL.
- Preserve the double-entry journal, reservations, idempotency and transaction-bound authorization.
- Keep PayPal Sandbox payments separate from simulated internal wallet funds.
- Reuse existing components and services; do not rewrite unrelated code.

## Payment safety

- AI may interpret requests and prepare financial actions; it must never bypass human approval or expand previously approved authority.
- Never mark an external payment successful without provider-confirmed evidence. Configuration, mocks and OAuth success are not payment evidence.
- Never invent merchant verification, balances or payment outcomes.
- PayPal-funded payments must never debit or reserve simulated internal wallet funds.
- Never weaken financial policies, limits or authorization to simplify a demo.

## Development

- Inspect relevant implementation, documentation and tests before editing; make small, focused changes.
- Avoid new dependencies unless the need and tradeoffs are justified.
- Never modify or reveal private `.env` credentials; use `.env.example` for documented configuration changes.
- Never run destructive database reset commands or delete database volumes. Protect development data.
- Keep simulated/demo and PayPal Sandbox labels explicit.
- Do not push automatically.
- Explain every file changed and report each validation result accurately.

## Testing

- Run relevant pytest tests from `backend`: `python -m pytest -q`.
- Run TypeScript checking and the Vite production build from `frontend`: `npm.cmd run build`.
- Run the existing Playwright verification from `frontend`: `node scripts/verify-product.mjs`.
- Financial changes require the isolated PostgreSQL integration suite in `docker-compose.test.yml`, never the development database. Inspect its commands first; if they require a destructive reset, report the conflict instead of running it.
- Report passed, failed, skipped and unexecuted checks separately, including blockers. Never count skipped provider or PostgreSQL tests as passed.
