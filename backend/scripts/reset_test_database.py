"""Reset only the disposable Compose PostgreSQL test schema."""
import os
from sqlalchemy import create_engine,text

url=os.environ.get("TEST_DATABASE_URL","")
if "aiwallet_test:test" in url or "@test-db:5432/aiwallet_test" not in url:
    raise SystemExit("Refusing to reset a database outside the isolated test-db service")
engine=create_engine(url)
with engine.begin() as connection:
    connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
    connection.execute(text("CREATE SCHEMA public"))
engine.dispose()
