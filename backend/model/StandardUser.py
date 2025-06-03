from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import Session

from backend.Service.ErrorHandler import fastapi_error_handler
from database import Base
from backend.model.Locker import Locker
from backend.model.LockerRoom import LockerRoom
from backend.model.LockerLog import log_unlock_action
from backend.websocket_broadcast import broadcast_message


class StandardUser(Base):
    __tablename__ = "standard_users"

    id = Column(Integer, primary_key=True, index=True)
    rfid_tag = Column(String, unique=True, nullable=True)

async def create_standard_user(rfid_tag: str, db: Session):
    """
    Oppretter en ny standardbruker.
    """
    existing_user = db.query(StandardUser).filter(StandardUser.rfid_tag == rfid_tag).first()
    if existing_user:
        raise fastapi_error_handler("rfid_tag finnes allerede.", status_code=400)

    new_user = StandardUser(rfid_tag=rfid_tag)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    await broadcast_message("update")

    return new_user

def get_user_by_rfid_tag(rfid_tag: str, db: Session):
    """
    Henter en bruker basert på rfid_tag.
    """
    return db.query(StandardUser).filter(StandardUser.rfid_tag == rfid_tag).first()

async def reserve_locker(user_id: int, locker_room_id: int, db: Session):
    """
    Reserverer et ledig skap i et spesifikt garderoberom for en bruker.
    Brukeren kan kun ha ett skap om gangen.
    """
    # 1. Sjekk om brukeren finnes
    user = db.query(StandardUser).filter(StandardUser.id == user_id).first()
    if not user:
        raise fastapi_error_handler("Brukeren finnes ikke.", status_code=404)

    # 2. Sjekk om brukeren allerede har et skap
    existing_locker = db.query(Locker).filter(
        Locker.user_id == user_id,
        Locker.status.ilike("Opptatt")
    ).first()

    if existing_locker:
        raise fastapi_error_handler(
            f"Brukeren har allerede et skap: {existing_locker.combi_id}", status_code=400
        )

    # 3. Sjekk om garderoberommet finnes
    room = db.query(LockerRoom).filter(LockerRoom.id == locker_room_id).first()
    if not room:
        raise fastapi_error_handler("Garderoberommet finnes ikke.", status_code=404)

    # 4. Finn ledig skap
    locker = db.query(Locker).filter(
        Locker.status.ilike("Ledig"),
        Locker.locker_room_id == locker_room_id
    ).order_by(Locker.combi_id.asc()).first()

    if not locker:
        raise fastapi_error_handler(f"Ingen ledige garderobeskap i rom '{room.name}'.", status_code=400)

    # 5. Reserver skap
    locker.status = "Opptatt"
    locker.user_id = user.id
    db.commit()
    from backend.model.LockerLog import log_reserved_action
    await log_reserved_action(locker_id=locker.id, user_id=user.id, db=db)

    db.refresh(locker)

    await broadcast_message("update")

    return {
        "message": f"Garderobeskap {locker.combi_id} i rom '{room.name}' er nå reservert for bruker med RFID {user.id}."
    }

async def unlock_locker(user_id: int, db: Session):
    locker = db.query(Locker).filter(Locker.user_id == user_id, Locker.status == "Opptatt").first()
    if not locker:
        raise fastapi_error_handler("Ingen opptatt garderobeskap funnet for denne brukeren.", status_code=404)

    locker.status = "Ledig"
    locker.user_id = None
    db.commit()
    db.refresh(locker)

    await log_unlock_action(locker_id=locker.combi_id, user_id=user_id, db=db)

    await broadcast_message("update")

    return {"message": f"Garderobeskap {locker.combi_id} er nå frigjort og tilgjengelig for andre brukere."}


async def manual_release_locker(user_id: int, db: Session):
    locker = db.query(Locker).filter(Locker.user_id == user_id, Locker.status == "Opptatt").first()
    if not locker:
        raise fastapi_error_handler("Ingen skap funnet som er i bruk av denne brukeren.", status_code=404)

    locker.status = "Ledig"
    locker.user_id = None
    db.commit()
    db.refresh(locker)

    from backend.model.LockerLog import log_action
    await log_action(locker_id=locker.id, user_id=user_id, action="Manuelt frigjort", db=db)

    await broadcast_message("update")

    return {"message": f"Skap {locker.combi_id} er manuelt frigjort av bruker {user_id}."}


async def temporary_unlock(user_id: int, db: Session):

    locker = db.query(Locker).filter(Locker.user_id == user_id, Locker.status == "Opptatt").first()
    if not locker:
        raise fastapi_error_handler("Ingen skap funnet som er i bruk av denne brukeren.", status_code=404)

    from backend.model.LockerLog import log_action
    await log_action(locker_id=locker.id, user_id=user_id, action="Låst opp", db=db)

    await broadcast_message("update")

    return {"message": f"Skap {locker.combi_id} er midlertidig åpnet for bruker {user_id}."}


async def lock_locker_after_use(user_id: int, db: Session):
    locker = db.query(Locker).filter(Locker.user_id == user_id, Locker.status == "Opptatt").first()
    if not locker:
        raise fastapi_error_handler("Ingen opptatt skap funnet for denne brukeren.", status_code=404)

    from backend.model.LockerLog import log_lock_action
    await log_lock_action(locker_id=locker.id, user_id=user_id, db=db)

    await broadcast_message("update")

    return {"message": f"Skap {locker.combi_id} er nå låst igjen for bruker {user_id}."}

async def scan_rfid_action(rfid_tag: str, locker_room_id: int, db: Session):
    """
    Hovedfunksjon: Brukes når RFID-skanning skjer.
    Hvis bruker har opptatt skap, åpne det (frigjøre).
    Hvis ikke, reserver nytt skap.
    """
    user = get_user_by_rfid_tag(rfid_tag, db)
    if not user:
        # Registrer bruker automatisk hvis ukjent kort
        user = await create_standard_user(rfid_tag, db)

    # Sjekk om brukeren har et skap
    existing_locker = db.query(Locker).filter(
        Locker.user_id == user.id,
        Locker.status.ilike("Opptatt")
    ).first()

    if existing_locker:
        # Brukeren har allerede et skap, så åpne det
        return await unlock_locker(user.id, db)
    else:
        # Brukeren har ikke et skap, så reserver et nytt
        return await reserve_locker(user.id, locker_room_id, db)

    # WebSocket-varsling håndteres i unlock_locker og reserve_locker
