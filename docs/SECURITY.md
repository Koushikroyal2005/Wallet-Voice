# Security

Secrets are backend environment variables and are never exposed to Vite. The production implementation must use verified WebAuthn assertions bound to a canonical transaction payload. `DEMO_AUTH_MODE` must be false outside local development.

The repository is structured to keep interpretation separate from execution. Model outputs must be validated against an explicit tool allowlist before a financial operation is created.
