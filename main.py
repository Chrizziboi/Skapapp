import os
import uvicorn
import logging

from database import SessionLocal, setup_database

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from backend.model import LockerRoom
from backend.model import Locker
from backend.model.Statistic import *
from backend.model.AdminUser import create_admin
from backend.model.StandardUser import reserve_locker
from backend.model.Locker import Locker, add_locker, add_note_to_locker, add_multiple_lockers
from backend.model.LockerRoom import create_locker_room
from backend.Service.ErrorHandler import fastapi_error_handler


# Initialiser SQLite3
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

# Oppsett for logging av feil
logging.basicConfig(level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s")

# Dependency for databaseøkter
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

''' FRONTPAGE '''

@api.get("/")
def serve_main_page_endpoint(request: Request):
    """
    Serverer main_page.html som hovedsiden.
    """
    try:
      return templates.TemplateResponse("main_page.html", {"request": request})
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av hovedsiden. {str(e)}", status_code=500)

''' SUBPAGES '''

@api.get("/available_lockers")
def serve_standard_user_page_endpoint(request: Request):
    """
    Serverer standard_user_page.html for vanlige brukere.
    """
    try:
        return templates.TemplateResponse("standard_user_page.html", {"request": request})
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av brukersiden. {str(e)}", status_code=500)


@api.get("/admin_page")
def serve_admin_page_endpoint(request: Request):
    """
    Serverer admin_page.html for admin-brukere.
    """
    try:
        return templates.TemplateResponse("admin_page.html", {"request": request})
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av adminsiden. {str(e)}", status_code=500)


@api.get("/admin_rooms")
def serve_admin_rooms_endpoint(request: Request):
    """
    Serverer admin_rooms.html for admin-brukere.
    """
    try:
        return templates.TemplateResponse("admin_rooms.html", {"request": request})
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av rom-siden. {str(e)}", status_code=500)


@api.get("/admin_lockers")
def serve_admin_lockers_endpoint(request: Request):
    """
    Serverer admin_lockers.html for admin-brukere.
    """
    return templates.TemplateResponse("admin_lockers.html", {"request": request})


''' GET CALLS '''

@api.get("/locker_rooms/")
def get_all_rooms_endpoint(db: Session = Depends(get_db)):
    """
    Endepunkt for å hente ALLE garderoberommene med riktige navn.
    """
    try:
        rooms = db.query(LockerRoom).all()
        return [{"room_id": room.id, "name": room.name} for room in rooms]
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av garderoberom: {str(e)}", status_code=500)

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


@api.get("/locker_rooms/{locker_room_id}/available_lockers")
def get_available_lockers_endpoint(locker_room_id: int, db: Session = Depends(get_db)):
    """
    Endepunkt for å hente antall ledige skap i et spesifikt garderoberom.
    """
    available_lockers = db.query(Locker).filter(
        Locker.locker_room_id == locker_room_id,
        Locker.status.ilike("ledig")
    ).count()
    try:
        return {"locker_room_id": locker_room_id, "available_lockers": available_lockers}
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av garderobeskap: {str(e)}", status_code=500)


@api.get("/lockers/")
def get_all_lockers_endpoint(db: Session = Depends(get_db)):
    """
    Endepunkt for å hente ALLE skap.
    """
    try:
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
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av garderoberom: {str(e)}", status_code=500)


''' POST CALLS '''

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


@api.post("/lockers/multiple_lockers")
def create_multiple_lockers_endpoint(locker_room_id: int, quantity: int, db: Session = Depends(get_db)):
    """
    Endepunkt for å opprette flere nye autogenerert garderobeskap i et garderoberom.
    """
    try:
        multiple_lockers = add_multiple_lockers(locker_room_id, quantity, db)
        return multiple_lockers
    except Exception as e:
        return fastapi_error_handler(f"Feil ved oppretting av garderobeskap: {str(e)}", status_code=500)


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

''' PUT CALLS '''

@api.put("/lockers/locker_id/note")
def update_locker_note_endpoint(locker_id: int, note: str, db: Session = Depends(get_db)):
    """
    Endepunkt for å legge til eller oppdatere et notat på et garderobeskap.
    """
    try:
        locker = add_note_to_locker(locker_id=locker_id, note=note, db=db)
        if locker is None:
            raise HTTPException(status_code=404, detail="Locker not found")
        return {"message": "Notat lagt til", "locker_id": locker.id, "note": locker.note}
    except Exception as e:
        return fastapi_error_handler(f"Feil ved oppdatering av notat: {str(e)}", status_code=500)


@api.put("/lockers/{locker_id}/unlock")
def unlock_locker_endpoint(locker_id: int, db: Session = Depends(get_db)):
    """
    Endepunkt for å låse opp et skap eksternt.
    """
    try:
        locker = db.query(Locker).filter(Locker.id == locker_id).first()
        if locker is None:
            raise HTTPException(status_code=404, detail="Garderobeskap ikke funnet.")
        locker.status = "ledig"
        db.commit()
        db.refresh(locker)  # Sikrer at endringer reflekteres i objektet
        return {"message": f"Garderobeskap med id: {locker_id} er nå åpnet."}
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av garderoberom: {str(e)}", status_code=500)


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

''' DELETE CALLS '''

@api.delete("/lockers/{locker_id}")
def remove_locker_endpoint(locker_id: int, db: Session = Depends(get_db)):
    """

    """
    try:
        locker = db.query(Locker).filter(Locker.id == locker_id).first()
        if not locker:
            raise HTTPException(status_code=404, detail="Garderobeskap ikke funnet.")
        db.delete(locker)
        db.commit()
        return {"message": f"Garderobeskap med id: {locker_id} har blitt slettet."}
    except Exception as e:
        return fastapi_error_handler(f"Feil ved sletting av garderoberom: {str(e)}", status_code=500)


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
        return {"message": f"Garderoberom {LockerRoom.name} er nå slettet."}
    except Exception as e:
        db.rollback()  # Sørger for at feilen ikke etterlater en halvferdig transaksjon.
        return fastapi_error_handler(f"En feil har oppstått under sletting av garderoberom: {str(e)}", status_code=500)

''' STATISTIC CALLS '''

@api.get("/statistic/total_lockers")
def get_total_lockers(db: Session = Depends(get_db)):
    try:
        return {"total_lockers": Statistic.total_lockers(db)}
    except Exception as e:
        logging.error(f"Feil ved henting av total antall skap: {str(e)}")
        raise HTTPException(status_code=500, detail="Kunne ikke hente total antall skap.")

@api.get("/statistic/available_lockers")
def get_available_lockers(db: Session = Depends(get_db)):
    try:
        return {"available_lockers": Statistic.available_lockers(db)}
    except Exception as e:
        logging.error(f"Feil ved henting av ledige skap: {str(e)}")
        raise HTTPException(status_code=500, detail="Kunne ikke hente ledige skap.")

@api.get("/statistic/occupied_lockers")
def get_occupied_lockers(db: Session = Depends(get_db)):
    try:
        return {"occupied_lockers": Statistic.occupied_lockers(db)}
    except Exception as e:
        logging.error(f"Feil ved henting av opptatte skap: {str(e)}")
        raise HTTPException(status_code=500, detail="Kunne ikke hente opptatte skap.")

@api.get("/statistic/total_users")
def get_total_users(db: Session = Depends(get_db)):
    try:
        return {"total_users": Statistic.total_users(db)}
    except Exception as e:
        logging.error(f"Feil ved henting av totalt antall brukere: {str(e)}")
        raise HTTPException(status_code=500, detail="Kunne ikke hente totalt antall brukere.")

@api.get("/statistic/lockers_by_room")
def get_lockers_by_room(db: Session = Depends(get_db)):
    try:
        return Statistic.lockers_by_room(db)
    except Exception as e:
        logging.error(f"Feil ved henting av skap per garderoberom: {str(e)}")
        raise HTTPException(status_code=500, detail="Kunne ikke hente skap per garderoberom.")

@api.get("/statistic/most_used_rooms")
def get_most_used_rooms(db: Session = Depends(get_db)):
    try:
        return Statistic.most_used_rooms(db)
    except Exception as e:
        logging.error(f"Feil ved henting av mest brukte garderoberom: {str(e)}")
        raise HTTPException(status_code=500, detail="Kunne ikke hente mest brukte garderoberom.")

@api.get("/statistic/most_active_users")
def get_most_active_users(db: Session = Depends(get_db)):
    try:
        return Statistic.most_active_users(db)
    except Exception as e:
        logging.error(f"Feil ved henting av mest aktive brukere: {str(e)}")
        raise HTTPException(status_code=500, detail="Kunne ikke hente mest aktive brukere.")


if __name__ == "__main__":
    uvicorn.run(
        "main:api",
        host="localhost",
        port=8080,
        reload=True
    )