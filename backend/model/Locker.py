from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import Session, relationship
from backend.Service.ErrorHandler import fastapi_error_handler
from database import Base


class Locker(Base):
    """
    Klasse for alle skap.
    """
    __tablename__ = "lockers"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(String, default="Ledig")
    note = Column(String, nullable=True)  #Legger til notatfelt
    user_id = Column(Integer, ForeignKey("standard_users.id", ondelete="SET NULL"), nullable=True)  #Knytter skap til en bruker

    locker_room_id = Column(Integer, ForeignKey("locker_rooms.id"))
    locker_room = relationship("LockerRoom", back_populates="lockers")


def add_locker(locker_room_id: int, db: Session):
    locker = Locker(locker_room_id=locker_room_id, status="Ledig")
    db.add(locker)
    db.commit()
    db.refresh(locker)
    return locker


def add_multiple_lockers(locker_room_id: int, quantity: int, db: Session):
    """
    Legger til flere skap i et spesifikt garderoberom.
    """
    if quantity <= 0:
        raise fastapi_error_handler(status_code=400, detail="Antall skap må være større enn 0.")

    # Opprett alle skapene i en liste
    new_lockers = [Locker(locker_room_id=locker_room_id, status="Ledig") for _ in range(quantity)]

    # Lagre alle skapene i databasen
    db.bulk_save_objects(new_lockers)
    db.commit()

    # Hent skapene PÅ NYTT fra databasen for å få riktige ID-er
    saved_lockers = db.query(Locker).filter(Locker.locker_room_id == locker_room_id).order_by(Locker.id.desc()).limit(quantity).all()

    return {
        "message": f"{quantity} garderobeskap er opprettet i rom {locker_room_id}.",
        "locker_ids": [locker.id for locker in saved_lockers]
    }


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
