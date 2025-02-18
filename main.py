import uvicorn
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.models.locker import Locker, add_locker
from backend.models.locker_room import create_locker_room
from database import Base, engine, SessionLocal
from backend.exception_Service.error_handler import fastapi_error_handler

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
    try:
        return {"message": "Hello from Raspberry Pi and FastAPI!"}
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av hovedsiden. {str(e)}", status_code=500)

@api.post("/locker_rooms/")
def create_room(name: str, db: Session = Depends(get_db)):
    """
    Endepunkt for å opprette et nytt garderoberom.
    """
    try:
        locker_room = create_locker_room(name=name, db=db)
        return {"message": "Garderoberom opprettet", "navn": locker_room.name}
    except Exception as e:
        return fastapi_error_handler(f"Feil ved oppretting av nytt garderoberom. {str(e)}", status_code=500)


@api.post("/lockers/")
def create_locker(locker_room_id: int, db: Session = Depends(get_db)):
    """
    Endepunkt for å opprette et nytt autogenerert garderobeskap i et garderoberom.
    """
    locker = add_locker(locker_room_id=locker_room_id, db=db)
    return {"message": "Garderobeskap Opprettet", "garderobeskaps_id": locker.locker_room_id}
@api.post("/lockers/")
def create_locker(locker_room_id: int, db: Session = Depends(get_db)):
    """
    Endepunkt for å opprette et nytt autogenerert garderobeskap i et garderoberom.
    """
    try:
        locker = add_locker(locker_room_id=locker_room_id, db=db)
        return {"message": "Garderobeskap Opprettet", "garderobeskaps_id": locker.locker_room_id}
    except Exception as e:
        return fastapi_error_handler(f"Feil ved oppretting av garderobeskap: {str(e)}", status_code=500)


@api.get("/lockers/{locker_id}")
def read_locker(locker_id: int, db: Session = Depends(get_db)):
    """
    Endepunkt for å finne valgt garderobeskap.
    """
    try:
        locker = db.query(Locker).filter(Locker.id == locker_id).first()
        if locker is None:
            raise HTTPException(status_code=404, detail="Locker not found")
        return {"locker_id": locker.locker_id, "status": locker.status}
    except HTTPException as http_err:
        raise http_err  # Beholder riktig statuskode
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av garderobeskap: {str(e)}", status_code=500)

if __name__ == "__main__":
    uvicorn.run(
        "main:api",
        host="localhost",
        port=8080,
        reload=True
    )
