from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship, Session
from database import Base
from fastapi import HTTPException

class LockerRoom(Base):
    __tablename__ = "locker_rooms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    location = Column(String, default="None", index=True)

    lockers = relationship("Locker", back_populates="locker_room")


def create_locker_room(name: str, db: Session):
    """
    Oppretter et nytt garderoberom hvis det ikke allerede finnes.
    """
    # Sjekk om garderoberommet allerede finnes
    existing_room = db.query(LockerRoom).filter(LockerRoom.name == name).first()
    if existing_room:
        raise HTTPException(status_code=400, detail=f"Garderoberom med navn '{name}' Finnes allerede.")

    # Opprett og legg til et nytt garderoberom
    new_locker_room = LockerRoom(name=name)
    db.add(new_locker_room)
    db.commit()
    db.refresh(new_locker_room)
    return new_locker_room
