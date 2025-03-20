from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import Session
from database import Base
from fastapi import HTTPException
from backend.model.Locker import Locker
from backend.model.LockerRoom import LockerRoom

class StandardUser(Base):
    __tablename__ = "standard_users"

    id = Column(Integer, primary_key=True, index=True)
    rfid_tag = Column(String, unique=True, nullable=True)

def create_standard_user(rfid_tag: str, db: Session):
    """
    Oppretter en ny standardbruker.
    """
    existing_user = db.query(StandardUser).filter(StandardUser.rfid_tag == rfid_tag).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="rfid_tag finnes allerede.")

    new_user = StandardUser(rfid_tag=rfid_tag)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

def get_user_by_rfid_tag(rfid_tag: str, db: Session):
    """
    Henter en bruker basert på rfid_tag.
    """
    return db.query(StandardUser).filter(StandardUser.rfid_tag == rfid_tag).first()

def reserve_locker(user_id: int, locker_room_id: int, db: Session):
    """
    Reserverer det ledige skapet med lavest nummer i et spesifikt garderoberom for en bruker.
    """
    # Sjekk om brukeren finnes
    user = db.query(StandardUser).filter(StandardUser.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Brukeren finnes ikke. Registrer deg før du reserverer et skap.")

    # Sjekk om garderoberommet finnes
    room = db.query(LockerRoom).filter(LockerRoom.id == locker_room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Garderoberommet finnes ikke.")

    # Finn det ledige skapet med lavest nummer i det spesifikke garderoberommet
    locker = db.query(Locker).filter(
        Locker.status == "ledig",
        Locker.locker_room_id == locker_room_id
    ).order_by(Locker.locker_number.asc()).first()

    # Hvis ingen ledige skap finnes i dette rommet
    if not locker:
        raise HTTPException(status_code=400, detail=f"Ingen ledige garderobeskap i rom '{room.name}'.")

    # Oppdater skapstatus og knytt skapet til brukeren
    locker.status = "opptatt"
    locker.user_id = user.id
    db.commit()
    db.refresh(locker)

    return {"message": f"Garderobeskap {locker.locker_number} i rom '{room.name}' er nå reservert for bruker {user.username}."}
