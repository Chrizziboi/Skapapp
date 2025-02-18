import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from backend.models.locker import Locker, add_locker, add_note_to_locker
from backend.models.locker_room import locker_room, create_locker_room
from database import Base, engine, SessionLocal
from backend.exception_Service.error_handler import fastapi_error_handler
import os

# Opprett tabellene
Base.metadata.create_all(bind=engine)

# Initialiser FastAPI
api = FastAPI()

# Finn absolutt sti til prosjektets rotmappe
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Sett riktig sti til "static/"
static_path = os.path.join(BASE_DIR, "static")

# Koble statiske filer til FastAPI
api.mount("/static", StaticFiles(directory=static_path), name="static")
# Sett opp templating-motoren (Jinja2)
templates = Jinja2Templates(directory="templates")

# Dependency for databaseøkter
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@api.get("/")
def serve_main_page(request: Request):
    """
    Serverer main_page.html som hovedsiden.
    """
    try:
      return templates.TemplateResponse("main_page.html", {"request": request})
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av hovedsiden. {str(e)}", status_code=500)


@api.get("/available_lockers")
def serve_standard_user_page(request: Request):
    """
    Serverer standard_user_page.html for vanlige brukere.
    """

    return templates.TemplateResponse("standard_user_page.html", {"request": request})


@api.get("/admin_page")
def serve_admin_page(request: Request):
    """
    Serverer admin_page.html for admin-brukere.
    """
    return templates.TemplateResponse("admin_page.html", {"request": request})


@api.get("/locker_rooms/")
def get_all_rooms(db: Session = Depends(get_db)):
    """
    Endepunkt for å hente ALLE garderoberommene med riktige navn.
    """
    rooms = db.query(locker_room).all()
    return [{"room_id": room.id, "name": room.name} for room in rooms]


@api.post("/locker_rooms/")
def create_room(name: str, db: Session = Depends(get_db)):
    """
    Endepunkt for å opprette et nytt garderoberom.
    """
    try:

      locker_room = create_locker_room(name=name, db=db)
      return {"message": "Garderoberom opprettet", "room_id": locker_room.id, "name": locker_room.name}
    except Exception as e:
        return fastapi_error_handler(f"Feil ved oppretting av nytt garderoberom. {str(e)}", status_code=500)


@api.get("/lockers/")
def get_all_lockers(db: Session = Depends(get_db)):
    """
    Endepunkt for å hente ALLE skap.
    """
    lockers = db.query(Locker).all()
    return [
        {"locker_id": locker.id, "status": locker.status, "user_id": locker.user_id}
        for locker in lockers
    ]


@api.post("/lockers/")
def create_locker(locker_room_id: int, db: Session = Depends(get_db)):
    """
    Endepunkt for å opprette et nytt autogenerert garderobeskap i et garderoberom.
    """
    locker = add_locker(locker_room_id=locker_room_id, db=db)
    return {"message": "Garderobeskap Opprettet", "garderobeskaps_id": locker_room_id}

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


@api.get("/lockers/locker_id")
def read_locker(locker_id: int, db: Session = Depends(get_db)):
    """
    Endepunkt for å finne valgt garderobeskap.
    """
    try:
      locker = db.query(Locker).filter(Locker.id == locker_id).first()
      if locker is None:
          raise HTTPException(status_code=404, detail="Skap ikke funnet")
      return {"locker_id": locker.id, "status": locker.status, "note": locker.note}
    except HTTPException as http_err:
        raise http_err  # Beholder riktig statuskode
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av garderobeskap: {str(e)}", status_code=500)


@api.put("/lockers/locker_id/note")
def update_locker_note(locker_id: int, note: str, db: Session = Depends(get_db)):
    """
    Endepunkt for å legge til eller oppdatere et notat på et garderobeskap.
    """
    locker = add_note_to_locker(locker_id=locker_id, note=note, db=db)
    if locker is None:
        raise HTTPException(status_code=404, detail="Locker not found")
    return {"message": "Notat lagt til", "locker_id": locker.id, "note": locker.note}


@api.get("/locker_rooms/{locker_room_id}/available_lockers")
def get_available_lockers(locker_room_id: int, db: Session = Depends(get_db)):
    """
    Endepunkt for å hente antall ledige skap i et spesifikt garderoberom.
    """
    available_lockers = db.query(Locker).filter(
        Locker.locker_room_id == locker_room_id,
        Locker.status.ilike("ledig")
    ).count()

    return {"locker_room_id": locker_room_id, "available_lockers": available_lockers}


@api.put("/lockers/{locker_id}/unlock")
def unlock_locker(locker_id: int, db: Session = Depends(get_db)):
    """
    Endepunkt for å låse opp et skap eksternt.
    """
    locker = db.query(Locker).filter(Locker.id == locker_id).first()
    if locker is None:
        raise HTTPException(status_code=404, detail="Locker not found")

    locker.status = "ledig"
    db.commit()
    return {"message": f"Locker {locker_id} has been unlocked."}


if __name__ == "__main__":
    uvicorn.run(
        "main:api",
        host="localhost",
        port=8080,
        reload=True
    )