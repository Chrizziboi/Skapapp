import os
import uvicorn

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from sqlalchemy.orm import Session

from backend.models.AdminUser import AdminUser, create_admin
from backend.models.StandardUser import StandardUser, reserve_locker
from backend.models import LockerRoom
from backend.models.Locker import Locker, add_locker, add_note_to_locker
from backend.models.LockerRoom import create_locker_room
from backend.ExceptionService.ErrorHandler import fastapi_error_handler
from database import Base, engine, SessionLocal, setup_database



setup_database()

# Initialiser FastAPI
api = FastAPI()

# Dynamisk sti til static-mappen, slik at det fungerer uansett hvor testen kjører fra
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

api.mount("/static", StaticFiles(directory=static_dir), name="static")

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
def serve_main_page_endpoint(request: Request):
    """
    Serverer main_page.html som hovedsiden.
    """
    try:
      return templates.TemplateResponse("main_page.html", {"request": request})
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av hovedsiden. {str(e)}", status_code=500)


@api.get("/available_lockers")
def serve_standard_user_page_endpoint(request: Request):
    """
    Serverer standard_user_page.html for vanlige brukere.
    """

    return templates.TemplateResponse("standard_user_page.html", {"request": request})


@api.get("/admin_page")
def serve_admin_page_endpoint(request: Request):
    """
    Serverer admin_page.html for admin-brukere.
    """
    return templates.TemplateResponse("admin_page.html", {"request": request})


@api.get("/admin_rooms")
def serve_admin_rooms_endpoint(request: Request):
    """
    Serverer admin_rooms.html for admin-brukere.
    """
    return templates.TemplateResponse("admin_rooms.html", {"request": request})


@api.get("/admin_lockers")
def serve_admin_lockers_endpoint(request: Request):
    """
    Serverer admin_lockers.html for admin-brukere.
    """
    return templates.TemplateResponse("admin_lockers.html", {"request": request})


@api.get("/locker_rooms/")
def get_all_rooms_endpoint(db: Session = Depends(get_db)):
    """
    Endepunkt for å hente ALLE garderoberommene med riktige navn.
    """
    rooms = db.query(LockerRoom).all()
    return [{"room_id": room.id, "name": room.name} for room in rooms]


@api.post("/locker_rooms/{name}")
def create_room_endpoint(name: str, db: Session = Depends(get_db)):
    """
    Endepunkt for å opprette et nytt garderoberom.
    """
    try:
        locker_room = create_locker_room(name=name, db=db)
        return {"message": "Garderoberom opprettet", "room_id": locker_room.id, "name": locker_room.name}
    except HTTPException as http_err:
        raise http_err  # Beholder riktig statuskode for allerede eksisterende rom
    except Exception as e:
        return fastapi_error_handler(f"Feil ved oppretting av nytt garderoberom: {str(e)}", status_code=500)


@api.delete("/locker_rooms/{room_id}")
def delete_room_endpoint(room_id: int, db: Session = Depends(get_db)):
    """
    Slett et garderoberom.
    """
    room = db.query(LockerRoom).filter(LockerRoom.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail=f"Garderoberom med id: {room_id} ikke funnet.")
    try:
        db.delete(room)
        db.commit()
        return {"message": "Garderoberom er nå slettet."}
    except Exception as e:
        db.rollback()  # Sørger for at feilen ikke etterlater en halvferdig transaksjon.
        raise HTTPException(status_code=500, detail=f"En feil har oppstått under sletting av garderoberom: {str(e)}")


@api.get("/lockers/")
def get_all_lockers_endpoint(db: Session = Depends(get_db)):
    """
    Endepunkt for å hente ALLE skap.
    """
    lockers = db.query(Locker).all()
    return [
        {
            "locker_id": locker.id,
            "locker_room_id": locker.locker_room_id,  # Legger til rom-ID
            "status": locker.status,
            "note": locker.note if locker.note else "N/A"  # Hvis notat er None, sett "N/A"
        }
        for locker in lockers
    ]


@api.post("/lockers/")
def create_locker_endpoint(locker_room_id: int, db: Session = Depends(get_db)):
    """
    Endepunkt for å opprette et nytt autogenerert garderobeskap i et garderoberom.
    """
    try:
        locker = add_locker(locker_room_id=locker_room_id, db=db)
        return {"message": "Garderobeskap Opprettet", "locker_id": locker.id}

    except Exception as e:
        return fastapi_error_handler(f"Feil ved oppretting av garderobeskap: {str(e)}", status_code=500)


@api.delete("/lockers/{locker_id}")
def remove_locker_endpoint(locker_id: int, db: Session = Depends(get_db)):
    locker = db.query(Locker).filter(Locker.id == locker_id).first()
    if not locker:
        raise HTTPException(status_code=404, detail="Garderobeskap ikke funnet.")

    db.delete(locker)
    db.commit()
    return {"message": f"Garderobeskap med id: {locker_id} har blitt slettet."}



@api.get("/lockers/locker_id")
def read_locker_endpoint(locker_id: int, db: Session = Depends(get_db)):
    """
    Endepunkt for å finne valgt garderobeskap.
    """
    try:
      locker = db.query(Locker).filter(Locker.id == locker_id).first()
      if locker is None:
          raise HTTPException(status_code=404, detail="Garderobeskap ikke funnet.")
      return {"locker_id": locker.id, "status": locker.status, "note": locker.note}
    except HTTPException as http_err:
        raise http_err  # Beholder riktig statuskode
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av garderobeskap: {str(e)}", status_code=500)


@api.put("/lockers/locker_id/note")
def update_locker_note_endpoint(locker_id: int, note: str, db: Session = Depends(get_db)):
    """
    Endepunkt for å legge til eller oppdatere et notat på et garderobeskap.
    """
    locker = add_note_to_locker(locker_id=locker_id, note=note, db=db)
    if locker is None:
        raise HTTPException(status_code=404, detail="Locker not found")
    return {"message": "Notat lagt til", "locker_id": locker.id, "note": locker.note}


@api.get("/locker_rooms/{locker_room_id}/available_lockers")
def get_available_lockers_endpoint(locker_room_id: int, db: Session = Depends(get_db)):
    """
    Endepunkt for å hente antall ledige skap i et spesifikt garderoberom.
    """
    available_lockers = db.query(Locker).filter(
        Locker.locker_room_id == locker_room_id,
        Locker.status.ilike("ledig")
    ).count()

    return {"locker_room_id": locker_room_id, "available_lockers": available_lockers}


@api.put("/lockers/{locker_id}/unlock")
def unlock_locker_endpoint(locker_id: int, db: Session = Depends(get_db)):
    """
    Endepunkt for å låse opp et skap eksternt.
    """
    locker = db.query(Locker).filter(Locker.id == locker_id).first()
    if locker is None:
        raise HTTPException(status_code=404, detail="Garderobeskap ikke funnet.")

    locker.status = "ledig"
    db.commit()
    db.refresh(locker)  # Sikrer at endringer reflekteres i objektet
    return {"message": f"Garderobeskap med id: {locker_id} er nå åpnet."}


@api.put("/lockers/reserve")
def reserve_locker_endpoint(user_id: int, locker_room_id: int, db: Session = Depends(get_db)):
    """
    Reserverer det ledige skapet med lavest nummer i et spesifikt garderoberom for en bruker.
    """
    try:
        reserve_locker(user_id=user_id, locker_room_id=locker_room_id, db=db)
        return {"message": "Garderobeskap reservert!", "locker_id": Locker.id}
    except Exception as e:
        return fastapi_error_handler(f"Feil ved reservering av garderobeskap: {str(e)}", status_code=500)

@api.post("/admin_users/")
def create_admin_user(username: str, password: str, is_superadmin: bool, db: Session = Depends(get_db)):
    """
    Oppretter en ny administratorbruker.
    """
    try:
        admin = create_admin(username=username, password=password, is_superadmin=is_superadmin, db=db)
        return {"message": "Administrator opprettet", "admin_id": admin.id}
    except Exception as e:
        return fastapi_error_handler(f"Feil ved oppretting av administrator: {str(e)}", status_code=500)


if __name__ == "__main__":
    uvicorn.run(
        "main:api",
        host="localhost",
        port=8080,
        reload=True
    )
