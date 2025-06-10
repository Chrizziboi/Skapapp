import asyncio
import os
import threading
from contextlib import asynccontextmanager

import uvicorn
import logging
import RPi.GPIO as GPIO
from mfrc522 import SimpleMFRC522
import time
#RiV2 imports
from backend.model.AdminUser import create_admin, manual_release_locker
from RaspberryPi import reader_helper

#Main Imports
from backend.model.LockerLog import LockerLog
from backend.model.LockerLog import log_unlock_action, release_expired_lockers_logic
from backend.model import Locker
from backend.model.Statistic import *
from backend.model.AdminUser import *
from backend.model.StandardUser import reserve_locker
from backend.model.Locker import add_locker, add_note_to_locker, add_multiple_lockers
from backend.model.LockerRoom import create_locker_room, delete_locker_room
from backend.Service.ErrorHandler import fastapi_error_handler
from backend.model.AdminUser import authenticate_user
from backend.model.StandardUser import get_user_by_rfid_tag, create_standard_user
from backend.auth.auth_handler import create_access_token, decode_access_token, verify_password
from backend.auth.auth_schema import Token, UserLogin
from backend.websocket_broadcast import api as websocket_api

from fastapi import FastAPI, Depends, Request, HTTPException, Query, requests
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi import UploadFile, File
from fastapi.responses import FileResponse
from fastapi import Body
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from pydantic import BaseModel

# Imports for CSV export endpoint
from fastapi.responses import StreamingResponse
import csv
from datetime import datetime, timedelta
from io import StringIO

from database import SessionLocal, setup_database
from database import backup_database_to_json, restore_database_from_json



# Initialiser SQLite3

def run_reader_helper():
    """
    Starter RFID-leseren i en egen tråd slik at den ikke blokkerer hovedløkken.
    """
    thread = threading.Thread(target=reader_helper, daemon=True)
    thread.start()
    print("[DEBUG] RFID-leser er startet i bakgrunnstråd.")

setup_database()

# Initialiser async funksjonalitet
@asynccontextmanager
async def lifespan(_):
    asyncio.create_task(release_expired_loop())
    # asyncio.create_task(rfid_background_listener())
    run_reader_helper()
    #run_manual_release_thread()
    # print("[DEBUG] release_expired_loop STARTET")
    yield

# Initialiser FastAPI
api = FastAPI(lifespan=lifespan)

# Dynamisk sti til static-mappen, slik at det fungerer uansett hvor testen kjører fra
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

api.mount("/static", StaticFiles(directory=static_dir), name="static")

# Sett opp templating-motoren (Jinja2)
templates = Jinja2Templates(directory="templates")

# Oppsett for logging av feil
logging.basicConfig(level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")
api.include_router(websocket_api)


# Dependency for databaseøkter
async def get_db():
    db = SessionLocal()
    # print("[DEBUG] Kjører release_expired_lockers_logic...")
    released = await release_expired_lockers_logic(db)
    try:
        yield db
    finally:
        db.close()

''' FRONTPAGE '''


# Pydantic-modell for login
class LoginRequest(BaseModel):
    password: str


# Pydantic-modell for opprettelse av bruker
class CreateUserRequest(BaseModel):
    password: str
    role: str


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


async def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    return payload

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


@api.get("/admin_statistics")
def serve_statistics_page(request: Request):
    try:
        return templates.TemplateResponse("admin_statistics.html", {"request": request})
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av statistikk-siden. {str(e)}", status_code=500)

@api.get("/admin_log")
def serve_log_page(request: Request):
    try:
        return templates.TemplateResponse("admin_log.html", {"request": request})
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av logger.{str(e)}" , status_code=500)

@api.get("/admin_backup")
def serve_backup_page(request: Request):
    """
    Serverer admin_backup.html for backup og restore.
    """
    try:
        return templates.TemplateResponse("admin_backup.html", {"request": request})
    except Exception as e:
        return fastapi_error_handler(f"Feil ved lasting av admin_backup.html: {str(e)}", status_code=500)


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
        return fastapi_error_handler(f"Feil ved henting av garderoberom {str(e)}", status_code=500)


# Nytt endepunkt: Oversikt over rom med totalt og ledige skap
@api.get("/locker_rooms/overview")
def get_rooms_overview(db: Session = Depends(get_db)):
    """
    Returnerer alle rom med navn, opptatte, ledige og totalt antall skap.
    Brukes til oversikt/progress-bar.
    """
    try:
        rooms = Statistic.get_all_rooms(db)
        overview = []
        for room in rooms:
            room_id = room["room_id"] if isinstance(room, dict) else room.room_id
            name = room["name"] if isinstance(room, dict) else room.name

            # Hent totalt antall skap og antall ledige skap for rommet
            total = Statistic.total_lockers_in_room(room_id, db)["total_lockers"]
            available_raw = Statistic.available_lockers(room_id, db)

            # FIX: sørg for at available er et heltall
            if isinstance(available_raw, dict) and "available_lockers" in available_raw:
                available = available_raw["available_lockers"]
            else:
                available = available_raw

            overview.append({
                "room_id": room_id,
                "name": name,
                "total": total,
                "available": available,
                "occupied": total - available
            })
        return overview
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av oversikt: {str(e)}", status_code=500)

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
        return fastapi_error_handler(f"Feil ved henting av garderobeskap, {str(e)}", status_code=500)


@api.get("/locker_rooms/{locker_room_id}/available_lockers")
def get_available_lockers_endpoint(locker_room_id: int, db: Session = Depends(get_db)):
    """
    Endepunkt for å hente antall ledige skap i et spesifikt garderoberom.
    """
    try:
        available_lockers = Statistic.available_lockers(locker_room_id, db)
        return available_lockers
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av Garderobeskap med id: {Locker.combi_id}, {str(e)}",
                                     status_code=500)


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


@api.get("/locker_logs")
def get_all_logs(
    from_date: str = Query(None, description="Fra dato, f.eks. 2022-01-01"),
    to_date: str = Query(None, description="Til dato, f.eks. 2024-12-31"),
    db: Session = Depends(get_db)):
    try:
        query = db.query(LockerLog)
        # Filtrer på dato hvis spesifisert
        if from_date:
            query = query.filter(LockerLog.timestamp >= from_date)
        if to_date:
            # For å inkludere hele to_date-dagen kan du evt. plusse på ett døgn/tid
            query = query.filter(LockerLog.timestamp <= to_date + " 23:59:59")
        logs = query.order_by(LockerLog.timestamp.desc()).all()
        result = []
        for log in logs:
            combi_id = "-"
            if log.locker_id:
                locker = db.query(Locker).filter(Locker.id == log.locker_id).first()
                if locker:
                    combi_id = locker.combi_id or "-"
            result.append({
                "id": log.id,
                "combi_id": combi_id,
                "user_id": log.user_id,
                "action": log.action,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,})
        return result
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av logger. {str(e)}", status_code=500)


@api.get("/lockers/occupied")
def get_occupied_lockers_endpoint(db: Session = Depends(get_db)):
    """
    Endepunkt for å hente ALLE skap som er opptatt.
    """
    try:
        occupied_lockers = Statistic.occupied_lockers(db)
        return occupied_lockers
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av opptatte skap: {str(e)}", status_code=500)


@api.get("/api/admin/data")
async def get_admin_data(current_user: dict = Depends(get_current_user)):
    try:
        if current_user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Not authorized")
        return {"data": "secure admin data"}
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av admin_data. {str(e)}", status_code=500)


''' POST CALLS '''


@api.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: SessionLocal = Depends(get_db)):
    try:
        user = authenticate_user(form_data.password, db)  # Merk kun bruk av password
        if not user:
            raise HTTPException(status_code=401, detail="Incorrect password")

        token_data = {"sub": str(user.id), "role": user.role}
        access_token = create_access_token(token_data)
        return {"access_token": access_token, "token_type": "bearer"}
    except Exception as e:
        return fastapi_error_handler(f"Feil ved innlogging. {str(e)}", status_code=500)


@api.post("/locker_rooms/{name}")
async def create_room_endpoint(name: str, db: Session = Depends(get_db)):
    """
    Endepunkt for å opprette et nytt garderoberom.
    """
    try:
        locker_room = await create_locker_room(name, db)
        await broadcast_message("update")
        return locker_room
    except Exception as e:
        return fastapi_error_handler(f"Feil ved oppretting av nytt garderoberom med id: {LockerRoom.id}: {str(e)}",
                                     status_code=500)


@api.post("/lockers/")
async def create_locker_endpoint(locker_room_id: int, db: Session = Depends(get_db)):
    try:
        result = await add_locker(locker_room_id, db)
        await broadcast_message("update")
        return result
    except Exception as e:
        return fastapi_error_handler(f"Feil ved oppretting av garderobeskap: {str(e)}", status_code=500)


@api.post("/lockers/multiple_lockers")
async def create_multiple_lockers_endpoint(locker_room_id: int, quantity: int, db: Session = Depends(get_db)):
    """
    Endepunkt for å opprette flere nye autogenerert garderobeskap i et garderoberom.
    """
    try:
        multiple_lockers = await add_multiple_lockers(locker_room_id, quantity, db)
        await broadcast_message("update")
        return multiple_lockers
    except Exception as e:
        return fastapi_error_handler(f"Feil ved oppretting av Garderobeskap med id: {Locker.combi_id}, {str(e)}",
                                     status_code=500)


@api.post("/admin_users/")
async def create_admin_user(request: CreateUserRequest = Body(...), db: Session = Depends(get_db)):
    try:
        admin = await create_admin(password=request.password, role=request.role, db=db)
        await broadcast_message("admin_created")
        return {
            "message": "Bruker opprettet",
            "role": admin.role
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@api.post("/scan_rfid/")
def scan_rfid(rfid_tag: str, locker_room_id: int, db: Session = Depends(get_db)):
    """
    Skann et RFID-kort. Reserver skap hvis mulig. Returner tilgangsbeskjed.
    """
    try:
        from backend.model.StandardUser import free_or_unlock_locker
        result = free_or_unlock_locker(rfid_tag, locker_room_id, db)
        return result
    except Exception as e:
        return fastapi_error_handler(f"Feil ved RFID-skanning: {str(e)}", status_code=400)


@api.post("/assign_after_closure/")
def assign_after_closure(rfid_tag: str, locker_room_id: int, locker_id: int, db: Session = Depends(get_db)):
    """
    Kalles etter manuell lukking → RFID skannes → skap reserveres hvis mulig.
    """
    try:
        from backend.model.StandardUser import assign_locker_after_manual_closure
        result = assign_locker_after_manual_closure(rfid_tag, locker_room_id, locker_id, db)
        return result
    except Exception as e:
        return fastapi_error_handler(f"Feil ved RFID-registrering etter lukking: {str(e)}", status_code=500)


''' PUT CALLS '''


@api.put("/lockers/{locker_id}/note")
async def update_locker_note_endpoint(locker_id: int, note: str, db: Session = Depends(get_db)):
    """
    Endepunkt for å legge til eller oppdatere et notat på et garderobeskap.
    """
    try:
        locker = await add_note_to_locker(locker_id=locker_id, note=note, db=db)
        if locker is None:
            raise fastapi_error_handler(f"Garderobeskap med id: {Locker.combi_id} ikke funnet", status_code=404)
        return locker
    except Exception as e:
        return fastapi_error_handler(f"Feil ved oppdatering av notat: {str(e)}", status_code=500)


# Denne skal nok byttes ut med temporary_unlock.
@api.put("/lockers/{locker_id}/unlock")
async def unlock_locker_endpoint(locker_id: int, db: Session = Depends(get_db)):
    """
    Endepunkt for å låse opp et skap eksternt og sette status til Ledig.
    """
    try:
        locker = db.query(Locker).filter(Locker.id == locker_id).first()
        if locker is None:
            raise fastapi_error_handler(f"Garderobeskap med id: {Locker.combi_id} ikke funnet.", status_code=404)

        locker.status = "Ledig"  # ← SETT DENNE!
        db.commit()
        db.refresh(locker)

        await log_unlock_action(locker_id=locker.id, user_id=locker.user_id, db=db)

        # Valgfritt: broadcast oppdatering slik at websockets fanger det
        await broadcast_message("update")

        return locker
    except Exception as e:
        return fastapi_error_handler(f"Feil ved opplåsing av skap: {str(e)}", status_code=500)


@api.put("/lockers/temporary_unlock")
async def temporary_unlock_endpoint(user_id: int, db: Session = Depends(get_db)):
    try:
        from backend.model.StandardUser import temporary_unlock
        return await temporary_unlock(user_id, db)
    except Exception as e:
        return fastapi_error_handler(f"Feil ved midlertidig opplåsning: {str(e)}", status_code=500)


@api.put("/lockers/lock_temporary_unlock")
async def lock_locker_after_use_endpoint(user_id: int, db: Session = Depends(get_db)):
    try:
        from backend.model.StandardUser import lock_locker_after_use
        return await lock_locker_after_use(user_id, db)
    except Exception as e:
        return fastapi_error_handler(f"Feil ved låsing av skap etter bruk: {str(e)}", status_code=500)


@api.put("/lockers/reserve")
async def reserve_locker_endpoint(user_id: int, locker_room_id: int, db: Session = Depends(get_db)):
    """
    Reserverer det ledige skapet med lavest nummer i et spesifikt garderoberom for en bruker.
    """
    try:
        reserved_locker = await reserve_locker(user_id=user_id, locker_room_id=locker_room_id, db=db)
        return reserved_locker
    except Exception as e:
        return fastapi_error_handler(f"Feil ved reservering av Garderobeskap med id: {Locker.combi_id}, {str(e)}",
                                     status_code=500)



@api.put("/lockers/manual_release/")
def manual_release_locker_endpoint(locker_id: int, locker_room_id: int, db: Session = Depends(get_db)):
    try:
        from backend.model.AdminUser import manual_release_locker
        result = manual_release_locker(locker_id, locker_room_id, db)
        # Hvis access_granted, kall Pi sitt REST-endepunkt:
        if result.get("access_granted"):
            try:
                PI_URL = "http://<PI_IP>:8000/api/manual_release"  # Sett riktig IP!
                r = requests.post(PI_URL, json={"locker_id": locker_id}, timeout=2)
                if r.status_code == 200:
                    result["pi_status"] = "OK"
                else:
                    result["pi_status"] = f"Feil fra Pi: {r.text}"
            except Exception as e:
                result["pi_status"] = f"Kunne ikke kontakte Pi: {str(e)}"
        return result
    except Exception as e:
        return fastapi_error_handler(f"Feil ved manuell frigjøring av skap: {str(e)}", status_code=500)

''' DELETE CALLS '''


@api.delete("/lockers/{locker_id}")
async def remove_locker_endpoint(locker_id: int, db: Session = Depends(get_db)):
    """
    Sletter et gitt skap fra et garderoberom.
    """
    try:
        from backend.model.Locker import remove_locker
        result = await remove_locker(locker_id, db)
        return result
    except Exception as e:
        return fastapi_error_handler(f"Feil ved sletting av garderobeskap med id: {Locker.combi_id}, {str(e)}",
                                     status_code=500)


@api.delete("/locker_rooms/{room_id}/lockers")
async def remove_all_lockers_in_room_endpoint(room_id: int, db: Session = Depends(get_db)):
    """
    Sletter alle garderobeskap i et spesifikt garderoberom.
    """
    try:
        from backend.model.Locker import remove_all_lockers_in_room
        result = await remove_all_lockers_in_room(room_id, db)
        return result
    except Exception as e:
        return fastapi_error_handler(f"Feil ved sletting av skap i garderoberom {room_id}: {str(e)}", status_code=500)


@api.delete("/locker_rooms/{room_id}")
async def delete_room_endpoint(room_id: int, db: Session = Depends(get_db)):
    """
    Sletter et garderoberom samt alle skap tilknyttet det rommet.
    """
    try:
        result = await delete_locker_room(room_id, db)
        return {
            "message": f"Garderoberom med ID {room_id} og alle tilhørende skap er slettet.",
            "room_id": room_id
        }
    except Exception as e:
        return fastapi_error_handler(f"Feil ved sletting av garderoberom: {str(e)}", status_code=500)

@api.delete("/admin_users/{admin_id}")
async def delete_admin_user(admin_id: int, db: Session = Depends(get_db)):
    try:
        result = delete_admin(admin_id, db)
        await broadcast_message("admin_deleted")  # Gir frontend beskjed om endring
        return {"message": f"Admin med ID {admin_id} er slettet."}
    except Exception as e:
        return fastapi_error_handler(f"Feil ved sletting av admin: {str(e)}", status_code=500)


''' STATISTIC CALLS '''


@api.get("/statistic/total_lockers")
def get_total_lockers(db: Session = Depends(get_db)):
    try:
        return {"total_lockers": Statistic.total_lockers(db)}
    except Exception as e:
        logging.error(f"Feil ved henting av total antall skap: {str(e)}")
        raise fastapi_error_handler("Kunne ikke hente total antall skap.", status_code=500)

@api.get("/statistic/available_lockers")
def get_total_available_lockers(db: Session = Depends(get_db)):
    try:
        count = db.query(Locker).filter(Locker.status.ilike("Ledig")).count()
        return {"available_lockers": count}
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av ledige skap: {str(e)}", 500)

@api.get("/statistic/available_lockers")
def get_available_lockers(db: Session = Depends(get_db)):
    try:
        available_lockers = Statistic.available_lockers(db)
        return available_lockers
    except Exception as e:
        logging.error(f"Feil ved henting av ledige skap: {str(e)}")
        raise fastapi_error_handler("Kunne ikke hente ledige skap.", status_code=500)


@api.get("/statistic/available_lockers_by_room/{room_id}")
def get_available_lockers_by_room(room_id: int, db: Session = Depends(get_db)):
    try:
        return Statistic.available_lockers(room_id, db)
    except Exception as e:
        return fastapi_error_handler(f"Feil ved romspesifikk henting av ledige skap: {str(e)}", 500)

@api.get("/statistic/occupied_lockers")
def get_occupied_lockers(db: Session = Depends(get_db)):
    try:
        count = Statistic.occupied_lockers(db)
        return {"occupied_lockers": count}
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av opptatte skap: {str(e)}", 500)


@api.get("/statistic/total_users")
def get_total_users(db: Session = Depends(get_db)):
    try:
        total_users = Statistic.total_users(db)

        return {"total_users": total_users}

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

@api.get("/statistic/all_lockers")
def get_all_lockers(db: Session = Depends(get_db)):
    try:
        return Statistic.all_lockers(db)
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av alle skap: {str(e)}", 500)

@api.get("/statistic/most_opened_lockers")
def get_most_opened_lockers(
    period: str = "month",
    db: Session = Depends(get_db)
):
    """
    Returnerer ALLE skap, med antall åpninger og sist åpnet (ev. 'Aldri åpnet').
    period: 'day', 'week', 'month' (default: month)
    """
    now = datetime.now()
    if period == "day":
        from_date = now - timedelta(days=1)
    elif period == "week":
        from_date = now - timedelta(weeks=1)
    elif period == "month":
        from_date = now - timedelta(days=30)
    else:
        from_date = None  # Da vises hele loggen

    # Venstre join for å få med ALLE skap
    subq = db.query(
        Locker.id.label("locker_id"),
        Locker.combi_id.label("combi_id"),
        func.count(LockerLog.id).label("times_opened"),
        func.max(LockerLog.timestamp).label("last_opened")
    ).outerjoin(
        LockerLog,
        (Locker.id == LockerLog.locker_id)
        & (LockerLog.action == "Låst opp")
        & ((LockerLog.timestamp >= from_date) if from_date else True)
    ).group_by(Locker.id, Locker.combi_id).subquery()

    results = db.query(
        subq.c.combi_id,
        subq.c.times_opened,
        subq.c.last_opened
    ).all()

    # Returnér alle skap, med antall åpninger og sist åpnet (kan være None/"Aldri åpnet")
    return [
        {
            "combi_id": combi_id,
            "times_opened": times_opened or 0,
            "last_opened": last_opened.isoformat() if last_opened else None
        }
        for combi_id, times_opened, last_opened in results
    ]


@api.get("/statistic/recent_log_entries")
def get_recent_log_entries(db: Session = Depends(get_db)):
    results = db.query(
        LockerLog.timestamp,
        Locker.combi_id,
        StandardUser.rfid_tag
    ).join(Locker, Locker.id == LockerLog.locker_id) \
        .outerjoin(StandardUser, LockerLog.user_id == StandardUser.id) \
        .order_by(LockerLog.timestamp.desc()) \
        .limit(10) \
        .all()

    return [
        {
            "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "combi_id": combi,
            "username": rfid
        }
        for ts, combi, rfid in results
    ]


@api.get("/statistic/most_used_rooms")
def get_most_used_rooms(db: Session = Depends(get_db)):
    try:
        most_used_rooms = Statistic.most_used_rooms(db)
        return most_used_rooms
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

@api.get("/statistic/users_with_usage")
def get_users_with_usage(db: Session = Depends(get_db)):
    try:
        all_users = db.query(StandardUser).all()
        logs = Statistic.most_active_users(db)
        log_map = {user["username"]: user["locker_count"] for user in logs}

        result = []
        for user in all_users:
            result.append({
                "username": user.rfid_tag,
                "locker_count": log_map.get(user.rfid_tag, 0)
            })
        return result
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av brukere med aktivitetsdata: {str(e)}", 500)

@api.get("/statistic/all_active_users_csv")
def download_all_active_users_csv(db: Session = Depends(get_db)):
    """
    Endepunkt for å laste ned alle brukere og deres antall reserveringer som CSV.
    """
    # Hent alle brukere med deres rfid-tag og antall reserveringer (bruker samme logikk som /statistic/most_active_users)
    results = db.query(
        StandardUser.id,
        StandardUser.rfid_tag,
        func.count(LockerLog.id)
    ).outerjoin(LockerLog, StandardUser.id == LockerLog.user_id)\
     .group_by(StandardUser.id, StandardUser.rfid_tag)\
     .order_by(func.count(LockerLog.id).desc()).all()

    output = StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(["Bruker-ID", "RFID-tag", "Antall reserveringer"])
    for user_id, rfid_tag, count in results:
        writer.writerow([user_id, rfid_tag or "-", count or 0])
    output.seek(0)

    filename = f"brukerliste_{datetime.now().strftime('%Y-%m-%d')}.csv"
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@api.get("/statistic/unique_users")
def get_unique_users(db: Session = Depends(get_db)):
    try:
        from backend.model.Statistic import get_unique_users_by_period
        return get_unique_users_by_period(db)
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av unike brukere: {str(e)}", 500)

# CSV-export endpoint for locker activity log
@api.get("/statistic/locker_activity_log")
def download_locker_activity_log_csv(period: str = "day", db: Session = Depends(get_db)):
    """
    Endepunkt for å laste ned skap-aktivitetlogg som CSV for 1 dag, 1 uke eller 1 måned.
    """
    now = datetime.now()
    if period == "day":
        from_date = now - timedelta(days=1)
    elif period == "week":
        from_date = now - timedelta(weeks=1)
    elif period == "month":
        from_date = now - timedelta(days=30)
    else:
        from_date = now - timedelta(days=1)  # default 1 dag

    logs = db.query(LockerLog).filter(LockerLog.timestamp >= from_date).order_by(LockerLog.timestamp.desc()).all()

    output = StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(["Bruker-ID", "Skap-ID", "Handling", "Tidspunkt"])
    for log in logs:
        if log.timestamp:
            ts = log.timestamp.strftime("%d/%m/%Y %H:%M:%S")
        else:
            ts = ""
        writer.writerow([log.user_id or "Ukjent", log.locker_id, log.action, ts])
    output.seek(0)

    filename = f"skap_aktivitetlogg_{period}_{now.strftime('%Y-%m-%d')}.csv"
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@api.get("/statistic/hourly_load")
def get_hourly_load(db: Session = Depends(get_db)):
    """
    Returnerer antall ganger skap har blitt åpnet (Låst opp) for hver time i døgnet de siste 30 dagene.
    """
    now = datetime.now()
    from_date = now - timedelta(days=30)

    # Hent alle logg-innslag siste 30 dager med action 'Låst opp'
    logs = db.query(LockerLog).filter(
        LockerLog.timestamp >= from_date,
        LockerLog.action == "Låst opp"
    ).all()

    # Lag 24 tellere for hver time i døgnet
    hourly_opens = [0] * 24

    # Tell antall åpninger per time (uansett dag)
    for log in logs:
        if log.timestamp:
            hour = log.timestamp.hour
            hourly_opens[hour] += 1

    # Returnér listen direkte (antall åpninger per time)
    total_lockers = db.query(Locker).count()
    return {
        "hourly_avg": hourly_opens,
        "total_lockers": total_lockers
    }

''' BACKUP CALLS '''


@api.get("/admin/backup", response_class=FileResponse)
def get_backup():
    """
    Eksporterer databasen til en JSON-fil og returnerer den.
    """
    try:
        backup_database_to_json("database.db", "backup_database.txt")
        return FileResponse("backup_database.txt", filename="skap_backup.json", media_type="application/json")
    except Exception as e:
        return fastapi_error_handler(f"Feil ved eksport av backup: {str(e)}", status_code=500)


@api.post("/admin/restore")
async def restore_from_backup(file: UploadFile = File(...)):
    """
    Gjenoppretter databasen fra en opplastet JSON-backup-fil.
    """
    try:
        contents = await file.read()
        with open("backup_database.txt", "wb") as f:
            f.write(contents)
        restore_database_from_json("database.db", "backup_database.txt")
        return {"message": "Databasen er gjenopprettet fra backup."}
    except Exception as e:
        return fastapi_error_handler(f"Feil ved gjenoppretting av backup: {str(e)}", status_code=500)

@api.get("/lockers/RBPI/occupied")
def get_raspberrypi_occupied_lockers_endpoint(db: Session = Depends(get_db)):
    """
    Endepunkt for å hente ALLE skap som er opptatt.
    """
    try:
        occupied_lockers = Statistic.raspberry_occupied_locker(db)
        return occupied_lockers
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av opptatte skap: {str(e)}", status_code=500)


''' Async Functions --- background processes '''


async def release_expired_loop():
    """
    Kjøres i bakgrunnen hvert 10. minutt for å frigjøre skap automatisk.
    """
    while True:
        db = None
        try:
            db = SessionLocal()
            released = release_expired_lockers_logic(db)
            if released:
                print(f"[Bakgrunnsjobb] Frigjorde {len(released)} skap:", released)
        except Exception as e:
            print(f"[Bakgrunnsjobb] Feil under frigjøring: {e}")
        finally:
            if db:
                db.close()

        await asyncio.sleep(5)  # 600 = 10 minutter


if __name__ == "__main__":
    uvicorn.run(
        "main:api",
        host="localhost",
        port=8080,
        reload=True
    )

# GPIO.cleanup()