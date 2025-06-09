from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship, Session

from backend.Service.ErrorHandler import fastapi_error_handler
from database import Base
from backend.model.Locker import Locker
from backend.websocket_broadcast import broadcast_message


class LockerRoom(Base):
    __tablename__ = "locker_rooms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    location = Column(String, default="None", index=True)

    lockers = relationship("Locker", back_populates="locker_rooms", cascade="all, delete-orphan")

async def create_locker_room(name: str, db: Session):
    """
    Oppretter et nytt garderoberom hvis det ikke allerede finnes.
    """
    existing_room = db.query(LockerRoom).filter(LockerRoom.name == name).first()
    if existing_room:
        raise fastapi_error_handler(f"Garderoberom med navn '{name}' finnes allerede.", status_code=400)

    new_locker_room = LockerRoom(name=name)
    db.add(new_locker_room)
    db.commit()
    db.refresh(new_locker_room)

    await broadcast_message("update")

    return {
        "message": f"Garderoberom '{new_locker_room.name}' opprettet.",
        "room_id": new_locker_room.id,
        "name": new_locker_room.name
    }

async def delete_locker_room(room_id: int, db: Session):
    """
    Sletter et garderoberom samt alle skap tilknyttet det rommet.
    """
    room = db.query(LockerRoom).filter(LockerRoom.id == room_id).first()
    if not room:
        raise fastapi_error_handler(f"Garderoberom med id {room_id} ikke funnet.", status_code=404)

    try:
        # Slett alle skap i rommet
        db.query(Locker).filter(Locker.locker_room_id == room_id).delete()

        # Slett selve rommet
        db.delete(room)
        db.commit()

        await broadcast_message("update")

        return {"message": f"Garderoberom med id {room_id} og tilhørende skap er nå slettet."}
    except Exception as e:
        db.rollback()  # Sørger for at feilen ikke etterlater en halvferdig transaksjon.
        raise fastapi_error_handler(f"En feil oppstod under sletting: {str(e)}", status_code=500)
