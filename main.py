import uvicorn
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database_functions.locker import Locker, add_locker
from database import Base, engine, SessionLocal

# Opprett tabellene
Base.metadata.create_all(bind=engine)

api = FastAPI()

# Dependency for databaseøkter
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@api.get("/")
def read_root():
    return {"message": "Hello from Raspberry Pi and FastAPI!"}

@api.post("/lockers/")
def create_locker(locker_id: int, status: str = "unlocked", is_active: bool = True, db: Session = Depends(get_db)):
    """
    Endepunkt for å opprette et nytt locker.
    """
    locker = add_locker(locker_id=locker_id, status=status, is_active=is_active, db=db)
    return {"message": "Locker created", "locker_id": locker.locker_id, "status": locker.status}

@api.get("/lockers/{locker_id}")
def read_locker(locker_id: int, db: Session = Depends(get_db)):
    locker = db.query(Locker).filter(Locker.locker_id == locker_id).first()
    if locker is None:
        raise HTTPException(status_code=404, detail="Locker not found")
    return {"locker_id": locker.locker_id, "status": locker.status}

if __name__ == "__main__":
    uvicorn.run(
        "main:api",
        host="localhost",
        port=8080,
        reload=True
    )
