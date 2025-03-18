from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import Session, relationship
from database import Base


class Locker(Base):
    __tablename__ = "lockers"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(String, default="Ledig")
    note = Column(String, nullable=True)  #Legger til notatfelt

    locker_room_id = Column(Integer, ForeignKey("locker_rooms.id"))
    locker_room = relationship("LockerRoom", back_populates="lockers")


def add_locker(locker_room_id: int, db: Session):
    locker = Locker(locker_room_id=locker_room_id, status="Ledig")
    db.add(locker)
    db.commit()
    db.refresh(locker)
    return locker


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


def remove_locker(locker_id: int, db: Session):
    locker = db.query(Locker).filter(Locker.id == locker_id).first()
    if locker:
        db.delete(locker)
        db.commit()
        return {"message": f"garderobeskap med id: {locker_id} har blitt slettet."}
    return {"error": "garderobeskap ikke funnet."}
