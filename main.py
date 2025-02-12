import uvicorn
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.models.locker import Locker, add_locker
from backend.models.locker_room import create_locker_room
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
    """
    Endepunkt for å komme til hovedsiden.
    """
    return {"message": "Hello from Raspberry Pi and FastAPI!"}


@api.post("/locker_rooms/")
def create_room(name: str, db: Session = Depends(get_db)):
    """
    Endepunkt for å opprette et nytt garderoberom.
    """
    locker_room = create_locker_room(name=name, db=db)
    return {"message": "Garderoberom opprettet", "rom_id": locker_room.id, "navn": locker_room.name}


@api.post("/lockers/")
def create_locker(locker_room_id: int, db: Session = Depends(get_db)):
    """
    Endepunkt for å opprette et nytt autogenerert garderobeskap i et garderoberom.
    """
    locker = add_locker(locker_room_id=locker_room_id, db=db)
    return {"message": "Garderobeskap Opprettet", "skap_id": locker.id, "garderobeskaps_id": locker.locker_room_id}


@api.get("/lockers/{id}")
def read_locker(locker_id: int, db: Session = Depends(get_db)):
    """
    Endepunkt for å finne valgt garderobeskap.
    """
    locker = db.query(Locker).filter(Locker.id == locker_id).first()
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
