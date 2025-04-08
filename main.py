import os
import uvicorn
import logging

from database import SessionLocal, setup_database

from fastapi import FastAPI, Depends, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from backend.model import Locker
from backend.model.Statistic import *
from backend.model.AdminUser import create_admin
from backend.model.StandardUser import reserve_locker
from backend.model.Locker import Locker, add_locker, add_note_to_locker, add_multiple_lockers
from backend.model.LockerRoom import create_locker_room, delete_locker_room
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


@api.get("/admin_wardrobe")
def serve_admin_wardrobe_management_endpoint(request: Request):

    try:
        return templates.TemplateResponse("admin_wardrobe_management.html", {"request": request})
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av siden. {str(e)}", status_code=500)

''' GET CALLS '''

@api.get("/locker_rooms/")
def get_all_rooms_endpoint(db: Session = Depends(get_db)):
    """
    Endepunkt for å hente ALLE garderoberommene med riktige navn.
    """
    try:
        rooms = Statistic.get_all_rooms(db)
        return rooms
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av garderoberom: {str(e)}", status_code=500)

@api.get("/lockers/locker_id")
def read_locker_endpoint(locker_id: int, db: Session = Depends(get_db)):
    """
    Endepunkt for å finne valgt garderobeskap.
    """
    try:
      locker = Statistic.read_locker(locker_id, db)
      if locker is None:
          raise fastapi_error_handler(f"Garderobeskap med id: {Locker.combi_id} ikke funnet.", status_code=404)
      return locker
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av garderobeskap med id: {Locker.combi_id}, {str(e)}", status_code=500)


@api.get("/locker_rooms/{locker_room_id}/available_lockers")
def get_available_lockers_endpoint(locker_room_id: int, db: Session = Depends(get_db)):
    """
    Endepunkt for å hente antall ledige skap i et spesifikt garderoberom.
    """
    try:
        available_lockers = Statistic.available_lockers(locker_room_id, db)
        return available_lockers
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av Garderobeskap med id: {Locker.combi_id}, {str(e)}", status_code=500)


@api.get("/lockers/")
def get_all_lockers_endpoint(db: Session = Depends(get_db)):
    """
    Endepunkt for å hente ALLE skap.
    """
    try:
        all_lockers = Statistic.all_lockers(db)
        return all_lockers
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av garderoberom: {str(e)}", status_code=500)


''' POST CALLS '''

@api.post("/locker_rooms/{name}")
def create_room_endpoint(name: str, db: Session = Depends(get_db)):
    """
    Endepunkt for å opprette et nytt garderoberom.
    """
    try:
        locker_room = create_locker_room(name, db)
        return locker_room
    except Exception as e:
        return fastapi_error_handler(f"Feil ved oppretting av nytt garderoberom med id: {LockerRoom.id}: {str(e)}", status_code=500)


@api.post("/lockers/")
def create_locker_endpoint(locker_room_id: int, db: Session = Depends(get_db)):
    """
    Endepunkt for å opprette et nytt autogenerert garderobeskap i et garderoberom.
    """
    try:
        result = add_locker(locker_room_id, db)
        return result
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
        return fastapi_error_handler(f"Feil ved oppretting av Garderobeskap med id: {Locker.combi_id}, {str(e)}", status_code=500)


@api.post("/admin_users/")
def create_admin_user(username: str, password: str, is_superadmin: bool, db: Session = Depends(get_db)):
    """
    Oppretter en ny administratorbruker.
    """
    try:
        admin = create_admin(username=username, password=password, is_superadmin=is_superadmin, db=db)
        return admin
    except Exception as e:
        return fastapi_error_handler(f"Feil ved oppretting av administrator: {str(e)}", status_code=500)

''' PUT CALLS '''

@api.put("/lockers/{locker_id}/note")
def update_locker_note_endpoint(locker_id: int, note: str, db: Session = Depends(get_db)):
    """
    Endepunkt for å legge til eller oppdatere et notat på et garderobeskap.
    """
    try:
        locker = add_note_to_locker(locker_id=locker_id, note=note, db=db)
        if locker is None:
            raise fastapi_error_handler(f"Garderobeskap med id: {Locker.combi_id} ikke funnet", status_code=404)
        return locker
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
            raise fastapi_error_handler(f"Garderobeskap med id: {Locker.combi_id} ikke funnet.", status_code=404)
        locker.status = "Ledig"
        db.commit()
        db.refresh(locker)  # Sikrer at endringer reflekteres i objektet
        return locker
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av garderoberom med id: {LockerRoom.id}, {str(e)}", status_code=500)


@api.put("/lockers/reserve")
def reserve_locker_endpoint(user_id: int, locker_room_id: int, db: Session = Depends(get_db)):
    """
    Reserverer det ledige skapet med lavest nummer i et spesifikt garderoberom for en bruker.
    """
    try:
        reserved_locker = reserve_locker(user_id=user_id, locker_room_id=locker_room_id, db=db)
        return reserved_locker
    except Exception as e:
        return fastapi_error_handler(f"Feil ved reservering av Garderobeskap med id: {Locker.combi_id}, {str(e)}", status_code=500)

''' DELETE CALLS '''

@api.delete("/lockers/{locker_id}")
def remove_locker_endpoint(locker_id: int, db: Session = Depends(get_db)):
    """
    Sletter et gitt skap fra et garderoberom.
    """
    try:
        locker = db.query(Locker).filter(Locker.id == locker_id).first()
        if not locker:
            raise fastapi_error_handler(f"Garderobeskap med id: {Locker.combi_id}, ikke funnet.", status_code=404)
        db.delete(locker)
        db.commit()
        return {"message": f"Garderobeskap med id: {Locker.combi_id} har blitt slettet."}
    except Exception as e:
        return fastapi_error_handler(f"Feil ved sletting av garderobeskap med id: {Locker.combi_id}, {str(e)}", status_code=500)


@api.delete("/locker_rooms/{room_id}/lockers")
def remove_all_lockers_in_room_endpoint(room_id: int, db: Session = Depends(get_db)):
    """
    Sletter alle garderobeskap i et spesifikt garderoberom.
    """
    try:
        from backend.model.Locker import remove_all_lockers_in_room
        result = remove_all_lockers_in_room(room_id, db)
        return result
    except Exception as e:
        return fastapi_error_handler(f"Feil ved sletting av skap i garderoberom {room_id}: {str(e)}", status_code=500)


@api.delete("/locker_rooms/{room_id}")
def delete_room_endpoint(room_id: int, db: Session = Depends(get_db)):
    """
    Sletter et garderoberom samt alle skap tilknyttet det rommet.
    """
    try:
        result = delete_locker_room(room_id, db)
        return {
            "message": f"Garderoberom med ID {room_id} og alle tilhørende skap er slettet.",
            "room_id": room_id
        }
    except Exception as e:
        return fastapi_error_handler(f"Feil ved sletting av garderoberom: {str(e)}", status_code=500)


''' STATISTIC CALLS '''

@api.get("/statistic/total_lockers")
def get_total_lockers(db: Session = Depends(get_db)):
    try:
        return {"total_lockers": Statistic.total_lockers(db)}
    except Exception as e:
        logging.error(f"Feil ved henting av total antall skap: {str(e)}")
        raise fastapi_error_handler("Kunne ikke hente total antall skap.", status_code=500)

@api.get("/statistic/available_lockers")
def get_available_lockers(db: Session = Depends(get_db)):
    try:
        return {"available_lockers": Statistic.available_lockers(db)}
    except Exception as e:
        logging.error(f"Feil ved henting av ledige skap: {str(e)}")
        raise fastapi_error_handler("Kunne ikke hente ledige skap.", status_code=500)

@api.get("/statistic/occupied_lockers")
def get_occupied_lockers(db: Session = Depends(get_db)):
    try:
        return {"occupied_lockers": Statistic.occupied_lockers(db)}
    except Exception as e:
        logging.error(f"Feil ved henting av opptatte skap: {str(e)}")
        raise fastapi_error_handler("Kunne ikke hente opptatte skap.", status_code=500)

@api.get("/statistic/total_users")
def get_total_users(db: Session = Depends(get_db)):
    try:
        return {"total_users": Statistic.total_users(db)}
    except Exception as e:
        logging.error(f"Feil ved henting av totalt antall brukere: {str(e)}")
        raise fastapi_error_handler("Kunne ikke hente totalt antall brukere.", status_code=500)

@api.get("/statistic/lockers_by_room")
def get_lockers_by_room(db: Session = Depends(get_db)):
    try:
        lockers_by_room = Statistic.lockers_by_room(db)
        return lockers_by_room
    except Exception as e:
        logging.error(f"Feil ved henting av skap per garderoberom: {str(e)}")
        raise fastapi_error_handler("Kunne ikke hente skap per garderoberom.", status_code=500)

@api.get("/statistic/most_used_rooms")
def get_most_used_rooms(db: Session = Depends(get_db)):
    try:
        most_used_rooms = Statistic.most_used_rooms(db)
        return most_used_rooms(db)
    except Exception as e:
        logging.error(f"Feil ved henting av mest brukte garderoberom: {str(e)}")
        raise fastapi_error_handler("Kunne ikke hente mest brukte garderoberom.", status_code=500)

@api.get("/statistic/most_active_users")
def get_most_active_users(db: Session = Depends(get_db)):
    try:
        most_active_users = Statistic.most_active_users(db)
        return most_active_users
    except Exception as e:
        logging.error(f"Feil ved henting av mest aktive brukere: {str(e)}")
        raise fastapi_error_handler("Kunne ikke hente mest aktive brukere.", status_code=500)
@api.get("/admin_statistics")
def serve_statistics_page(request: Request):
    try:
        return templates.TemplateResponse("admin_statistics.html", {"request": request})
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av statistikk-siden. {str(e)}", status_code=500)


if __name__ == "__main__":
    uvicorn.run(
        "main:api",
        host="localhost",
        port=8080,
        reload=True
    )