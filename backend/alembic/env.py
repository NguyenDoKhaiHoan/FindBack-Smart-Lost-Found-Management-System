from sqlalchemy import text

from alembic import context
from app.core.config import Settings
from app.db import models  # noqa: F401
from app.db.session import Base, make_engine

config = context.config


def run(connection):
    schema = config.attributes.get("schema")
    if schema is None and connection.dialect.name != "sqlite":
        schema = Settings().database_schema
    if schema:
        # Schema is an identifier, never interpolated without dialect quoting.
        quoted = connection.dialect.identifier_preparer.quote(schema)
        connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {quoted}"))
        connection.commit()
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        version_table_schema=schema,
        include_schemas=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations(schema=schema)


if context.is_offline_mode():
    raise RuntimeError("Use online migrations so schema and dialect are verified")
elif config.attributes.get("connection") is not None:
    run(config.attributes["connection"])
else:
    engine = make_engine(Settings())
    with engine.connect() as connection:
        run(connection)
    engine.dispose()
