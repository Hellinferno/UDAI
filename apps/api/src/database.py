from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

# We default to SQLite for immediate local dev compatibility without forcing the user to spin up Docker Postgres immediately,
# but the code is fully Postgres-ready based on the DB_URL format.
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./aibaa.db")

# SQLite requires this connect_args flag. Postgres does not.
connect_args = {"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args=connect_args
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
