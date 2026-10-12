import os
import re
from urllib.parse import quote_plus
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Load environment variables from .env file
load_dotenv()

def normalize_database_url(url: str) -> str:
    """
    Normalizes the database URL:
    1. Ensures dialect is postgresql:// instead of postgres://
    2. Gracefully handles passwords containing special characters (like '@')
    """
    if not url:
        return ""
    
    url = url.strip()
    
    # Handle postgres:// -> postgresql://
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    elif not url.startswith("postgresql://") and not url.startswith("sqlite://"):
        # If it doesn't have scheme, assume postgresql://
        url = "postgresql://" + url

    # If it's a postgresql URL, check for unescaped '@' in credentials
    if url.startswith("postgresql://"):
        without_scheme = url[len("postgresql://"):]
        # Find the last '@' which separates user:pass from host:port/dbname
        if "@" in without_scheme:
            credentials, host_part = without_scheme.rsplit("@", 1)
            if ":" in credentials:
                user, password = credentials.split(":", 1)
                # If password contains '@' or '+', make sure it is safely encoded
                # We unquote first to avoid double encoding if already encoded
                from urllib.parse import unquote
                clean_pass = quote_plus(unquote(password))
                url = f"postgresql://{user}:{clean_pass}@{host_part}"
                
    return url

DATABASE_URL = os.getenv("DATABASE_URL", "")

if not DATABASE_URL:
    # Fallback to local SQLite for immediate testing if no DATABASE_URL provided
    DATABASE_URL = "sqlite:///./food_rescue.db"
    print("Warning: DATABASE_URL not set in environment. Falling back to sqlite:///./food_rescue.db")
else:
    DATABASE_URL = normalize_database_url(DATABASE_URL)

# Configure SQLAlchemy engine
# SQLite requires check_same_thread=False, Postgres does not
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """
    Dependency generator for obtaining a database session.
    Ensures the session is cleanly closed after the request completes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
