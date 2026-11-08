# Docker setup

`docker compose up --build` launches PostgreSQL, API, expiry worker, and nginx-hosted frontend. The API creates demo tables at startup in this prototype; use Alembic migrations before any shared or production deployment.
