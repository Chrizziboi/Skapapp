from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, update, delete
from sqlalchemy.orm import Session, relationship
from database import Base

class Locker(Base):
    __tablename__ = "lockers"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(String, default="Ledig")
    is_active = Column(Boolean, default=False)
    note = Column(String, nullable=True)  # ✅ Legger til notatfelt

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


from sqlalchemy.orm import Session
from backend.models.locker import Locker


def add_note_to_locker(locker_id: int, note: str, db: Session):
    """
    Lar en administrator legge til eller oppdatere et notat på et spesifikt garderobeskap.
    """
    locker = db.query(Locker).filter(Locker.id == locker_id).first()

    if not locker:
        return None  # Returnerer None hvis skapet ikke finnes

    locker.note = note  # Oppdaterer notatet
    db.commit()
    db.refresh(locker)  # Oppdaterer objektet etter commit

    return locker

def remove_locker(locker_room_id: int, db: Session):
    db.execute(delete(Locker).where(Locker.id == locker_id))
    db.commit()