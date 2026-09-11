from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

from app.config import settings

engine = create_engine(f"sqlite:///{settings.db_path}", echo=False)

# SQLite type for each SQLModel field type we actually add after the fact.
_SQLITE_TYPES = {"JSON": "JSON", "VARCHAR": "VARCHAR", "FLOAT": "FLOAT", "INTEGER": "INTEGER"}


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    _add_missing_columns()


def _add_missing_columns() -> None:
    """Bring existing tables up to the current models.

    `create_all` only creates missing *tables*, so a column added to a model
    after a database exists is silently absent and every SELECT fails. There is
    no migration tool here yet; new nullable columns are the only schema change
    made so far, and SQLite can add those in place.
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table in SQLModel.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            have = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in have:
                    continue
                type_ = _SQLITE_TYPES.get(str(column.type).split("(")[0], "TEXT")
                conn.execute(
                    text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {type_}')
                )


def get_session():
    with Session(engine) as session:
        yield session
