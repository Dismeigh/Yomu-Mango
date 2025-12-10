from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# SQLite database file named manga.db in the project root
DATABASE_URL = "sqlite:///./manga.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # required for SQLite + FastAPI
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
