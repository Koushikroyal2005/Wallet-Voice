# Architecture

`React UI → FastAPI presentation → deterministic application services → SQLAlchemy persistence`. The financial service locks the wallet row during state changes, posts a balanced journal, creates expiring reservations before provider execution, and persists application events in the same transaction. Providers remain a replaceable infrastructure boundary.

## Financial flow

`intent → validation → policy trace → user confirmation / eligible demo route → ledger entry → operation result`

Money is represented in integer minor units. Each journal has separate debit and credit entries; completed records are append-only. Posted balance comes from wallet-liability credits less debits; available balance additionally subtracts active reservations.
