from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import Session, relationship
from database import Base

class Locker(Base):
    __tablename__ = "lockers"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(String, default="Ledig")
    is_active = Column(Boolean, default=False)

    locker_room_id = Column(Integer, ForeignKey("locker_rooms.id"))
    locker_room = relationship("locker_room", back_populates="lockers")


def locker_id():
    """
    Henter database id'en til et gitt garderobeskap.
    """
    return Locker.id


def add_locker(locker_room_id: int, db: Session):
    """
    Legger til et nytt garderobeskap til et gitt garderoberom.
    """
    max_locker_id = db.query(Locker.id).order_by(Locker.id.desc()).first()
    new_locker_id = (max_locker_id[0] + 1) if max_locker_id else 1

    locker = Locker(id=new_locker_id, locker_room_id=locker_room_id, status="Ledig", is_active=False)

    db.add(locker)
    db.commit()
    db.refresh(locker)

    return locker
