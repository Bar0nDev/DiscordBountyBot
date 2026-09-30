from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import Base

engine = create_engine("sqlite:///info.db", echo=True)
Base.metadata.create_all(engine)


def _ensure_schema():
    """Apply additive schema updates needed by restored mission/bounty cogs."""
    with engine.begin() as connection:
        columns = {
            row[1]
            for row in connection.exec_driver_sql("PRAGMA table_info(bounties)")
        }
        if "stars" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE bounties ADD COLUMN stars INTEGER DEFAULT 5"
            )


_ensure_schema()
Session = sessionmaker(bind=engine)
