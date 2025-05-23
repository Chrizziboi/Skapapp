import asyncio
import os
from contextlib import asynccontextmanager

import uvicorn
import logging

from backend.model.LockerLog import LockerLog
from backend.model.LockerLog import log_unlock_action, release_expired_lockers_logic
from backend.model import Locker
from backend.model.Statistic import *
from backend.model.AdminUser import create_admin
from backend.model.StandardUser import reserve_locker
from backend.model.Locker import add_locker, add_note_to_locker, add_multiple_lockers
from backend.model.LockerRoom import create_locker_room, delete_locker_room
from backend.Service.ErrorHandler import fastapi_error_handler
from backend.model.AdminUser import authenticate_user
from backend.model.StandardUser import get_user_by_rfid_tag, create_standard_user

from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi import UploadFile, File
from fastapi.responses import FileResponse
from fastapi import Body
from pydantic import BaseModel

from database import SessionLocal, setup_database
from database import backup_database_to_json, restore_database_from_json
# Initialiser SQLite3

setup_database()

# Initialiser async funksjonalitet
@asynccontextmanager
async def lifespan(_):
    asyncio.create_task(release_expired_loop())
    print("[DEBUG] release_expired_loop STARTET")
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


# Dependency for databaseøkter
def get_db():
    db = SessionLocal()
    print("[DEBUG] Kjører release_expired_lockers_logic...")
    released = release_expired_lockers_logic(db)
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
def get_all_logs(db: Session = Depends(get_db)):
    logs = db.query(LockerLog).all()
    return [
        {
            "locker_id": log.locker_id,
            "user_id": log.user_id,
            "action": log.action,
            "timestamp": log.timestamp
        }
        for log in logs
    ]
  

''' POST CALLS '''


@api.post("/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    Logger inn en bruker basert på pin/passord.
    """
    user = authenticate_user(request.password, db)
    if not user:
        raise HTTPException(status_code=401, detail="Ugyldig kode")

    return {
        "message": "Innlogging vellykket",
        "role": user.role
    }

@api.post("/locker_rooms/{name}")
def create_room_endpoint(name: str, db: Session = Depends(get_db)):
    """
    Endepunkt for å opprette et nytt garderoberom.
    """
    try:
        locker_room = create_locker_room(name, db)
        return locker_room
    except Exception as e:
        return fastapi_error_handler(f"Feil ved oppretting av nytt garderoberom med id: {LockerRoom.id}: {str(e)}",
                                     status_code=500)


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
        return fastapi_error_handler(f"Feil ved oppretting av Garderobeskap med id: {Locker.combi_id}, {str(e)}",
                                     status_code=500)


@api.post("/admin_users/")
def create_admin_user(request: CreateUserRequest = Body(...), db: Session = Depends(get_db)):
    """
    Oppretter en ny bruker med pin/passord og rolle.
    """
    try:
        admin = create_admin(password=request.password, role=request.role, db=db)
        return {
            "message": "Bruker opprettet",
            "role": admin.role
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@api.post("/scan_rfid/")
def scan_rfid(rfid_tag: str, db: Session = Depends(get_db)):
    """
    Skann et RFID-kort. Registrer bruker hvis ny. Returner alle ledige skap.
    """
    try:

        user = get_user_by_rfid_tag(rfid_tag, db)
        if not user:
            user = create_standard_user(rfid_tag, db)

        available_lockers = db.query(Locker).filter(Locker.status == "Ledig").all()

        return {
            "user_id": user.id,
            "available_lockers": [
                {"locker_id": locker.id, "combi_id": locker.combi_id, "locker_room_id": locker.locker_room_id}
                for locker in available_lockers
            ]
        }
    except Exception as e:
        return fastapi_error_handler(f"Feil ved skanning av RFID-kort: {str(e)}", status_code=400)


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
        db.commit()
        db.refresh(locker)  # Sikrer at endringer reflekteres i objektet

        log_unlock_action(locker_id=locker.id, user_id=locker.user_id, db=db)

        return locker
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av garderoberom med id: {LockerRoom.id}, {str(e)}",
                                     status_code=500)


@api.put("/lockers/temporary_unlock")
def temporary_unlock_endpoint(user_id: int, db: Session = Depends(get_db)):
    try:
        from backend.model.StandardUser import temporary_unlock
        return temporary_unlock(user_id, db)
    except Exception as e:
        return fastapi_error_handler(f"Feil ved midlertidig opplåsning: {str(e)}", status_code=500)


@api.put("/lockers/lock_temporary_unlock")
def lock_locker_after_use_endpoint(user_id: int, db: Session = Depends(get_db)):
    try:
        from backend.model.StandardUser import lock_locker_after_use
        return lock_locker_after_use(user_id, db)
    except Exception as e:
        return fastapi_error_handler(f"Feil ved låsing av skap etter bruk: {str(e)}", status_code=500)


@api.put("/lockers/temporary_unlock")
def temporary_unlock_endpoint(user_id: int, db: Session = Depends(get_db)):
    try:
        from backend.model.StandardUser import temporary_unlock
        return temporary_unlock(user_id, db)
    except Exception as e:
        return fastapi_error_handler(f"Feil ved midlertidig opplåsning: {str(e)}", status_code=500)


@api.put("/lockers/lock_temporary_unlock")
def lock_locker_after_use_endpoint(user_id: int, db: Session = Depends(get_db)):
    try:
        from backend.model.StandardUser import lock_locker_after_use
        return lock_locker_after_use(user_id, db)
    except Exception as e:
        return fastapi_error_handler(f"Feil ved låsing av skap etter bruk: {str(e)}", status_code=500)


@api.put("/lockers/reserve")
def reserve_locker_endpoint(user_id: int, locker_room_id: int, db: Session = Depends(get_db)):
    """
    Reserverer det ledige skapet med lavest nummer i et spesifikt garderoberom for en bruker.
    """
    try:
        reserved_locker = reserve_locker(user_id=user_id, locker_room_id=locker_room_id, db=db)
        return reserved_locker
    except Exception as e:
        return fastapi_error_handler(f"Feil ved reservering av Garderobeskap med id: {Locker.combi_id}, {str(e)}",
                                     status_code=500)


@api.put("/lockers/manual_release")
def manual_release_locker_endpoint(user_id: int, db: Session = Depends(get_db)):
    try:
        from backend.model.StandardUser import manual_release_locker
        return manual_release_locker(user_id, db)
    except Exception as e:
        return fastapi_error_handler(f"Feil ved manuell frigjøring av skap: {str(e)}", status_code=500)


@api.put("/lockers/manual_release")
def manual_release_locker_endpoint(user_id: int, db: Session = Depends(get_db)):
    try:
        from backend.model.StandardUser import manual_release_locker
        return manual_release_locker(user_id, db)
    except Exception as e:
        return fastapi_error_handler(f"Feil ved manuell frigjøring av skap: {str(e)}", status_code=500)


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
        return fastapi_error_handler(f"Feil ved sletting av garderobeskap med id: {Locker.combi_id}, {str(e)}",
                                     status_code=500)


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
        return fastapi_error_handler(f"Feil ved henting av total skap: {str(e)}", 500)



@api.get("/statistic/available_lockers")
def get_total_available_lockers(db: Session = Depends(get_db)):
    try:
        count = db.query(Locker).filter(Locker.status.ilike("Ledig")).count()
        return {"available_lockers": count}
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av ledige skap: {str(e)}", 500)



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
        return Statistic.lockers_by_room(db)
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av skap per rom: {str(e)}", 500)



@api.get("/statistic/most_opened_lockers")
def get_most_opened_lockers(db: Session = Depends(get_db)):
    results = db.query(
        Locker.combi_id,
        func.count(LockerLog.id).label("times_opened")
    ).join(LockerLog, Locker.id == LockerLog.locker_id)\
     .filter(LockerLog.action == "Låst opp")\
     .group_by(Locker.combi_id)\
     .order_by(func.count(LockerLog.id).desc())\
     .limit(10)\
     .all()

    return [{"combi_id": combi_id, "times_opened": count} for combi_id, count in results]



@api.get("/statistic/most_used_rooms")
def get_most_used_rooms(db: Session = Depends(get_db)):
    try:
        return Statistic.most_used_rooms(db)
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av mest brukte rom: {str(e)}", 500)



@api.get("/statistic/most_active_users")
def get_most_active_users(db: Session = Depends(get_db)):
    try:
        return Statistic.most_active_users(db)
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av mest aktive brukere: {str(e)}", 500)

@api.get("/statistic/available_lockers_by_room/{room_id}")
def get_available_lockers_by_room(room_id: int, db: Session = Depends(get_db)):
    try:
        return Statistic.available_lockers(room_id, db)
    except Exception as e:
        return fastapi_error_handler(f"Feil ved romspesifikk henting av ledige skap: {str(e)}", 500)

@api.get("/statistic/all_lockers")
def get_all_lockers(db: Session = Depends(get_db)):
    try:
        return Statistic.all_lockers(db)
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av alle skap: {str(e)}", 500)

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

@api.get("/statistic/recent_log_entries")
def get_recent_log_entries(db: Session = Depends(get_db)):
    try:
        return Statistic.latest_log_entries(db)
    except Exception as e:
        return fastapi_error_handler(f"Feil ved henting av logg: {str(e)}", 500)

        
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

        await asyncio.sleep(600)  # 10 minutter

if __name__ == "__main__":
    uvicorn.run(
        "main:api",
        host="localhost",
        port=8080,
        reload=True
    )