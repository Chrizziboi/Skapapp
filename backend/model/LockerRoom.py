from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship, Session

from database import Base
from fastapi import HTTPException
from backend.model.Locker import Locker  # Importer Locker-modellen

class LockerRoom(Base):
    __tablename__ = "locker_rooms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    location = Column(String, default="None", index=True)

    lockers = relationship("Locker", back_populates="locker_rooms", cascade="all, delete-orphan")

def create_locker_room(name: str, db: Session):
    """
    Oppretter et nytt garderoberom hvis det ikke allerede finnes.
    """
    existing_room = db.query(LockerRoom).filter(LockerRoom.name == name).first()
    if existing_room:
        raise HTTPException(status_code=400, detail=f"Garderoberom med navn '{name}' finnes allerede.")

    new_locker_room = LockerRoom(name=name)
    db.add(new_locker_room)
    db.commit()
    db.refresh(new_locker_room)
    return new_locker_room

def delete_locker_room(room_id: int, db: Session):
    """
    Sletter et garderoberom samt alle skap tilknyttet det rommet.
    """
    room = db.query(LockerRoom).filter(LockerRoom.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail=f"Garderoberom med id {room_id} ikke funnet.")

    try:
        # Slett alle skap i rommet
        db.query(Locker).filter(Locker.locker_room_id == room_id).delete()

        # Slett selve rommet
        db.delete(room)
        db.commit()

        return {"message": f"Garderoberom med id {room_id} og tilhørende skap er nå slettet."}
    except Exception as e:
        db.rollback()  # Sørger for at feilen ikke etterlater en halvferdig transaksjon.
        raise HTTPException(status_code=500, detail=f"En feil oppstod under sletting: {str(e)}")
