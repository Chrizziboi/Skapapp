from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# SQLite-database lagres i en fil
DATABASE_URL = "sqlite:///./database.db"

# Oppretter en database-motor
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Oppretter en session factory, der autocommit er valget om endringer i
# databasen skal lagres automatisk eller ikke etter en session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Deklarativ baseklasse for modeller
Base = declarative_base()
