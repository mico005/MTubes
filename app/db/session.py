from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

# Using SQLite for instant MVP testing. Swap to Postgres URI in .env later.
SQLALCHEMY_DATABASE_URL = "sqlite:///./music_clone.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={
        "check_same_thread": False,
        "timeout": 15
    }
)

# Enable Write-Ahead Logging (WAL) to allow simultaneous readers and one writer


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
