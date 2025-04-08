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
    combi_id = Column(String, nullable=True)
    status = Column(String, default="Ledig")
    note = Column(String, nullable=True)  #Legger til notatfelt
    user_id = Column(Integer, ForeignKey("standard_users.id", ondelete="SET NULL"), nullable=True)  #Knytter skap til en bruker

    locker_room_id = Column(Integer, ForeignKey("locker_rooms.id"))
    locker_rooms = relationship("LockerRoom", back_populates="lockers")


def add_locker(locker_room_id: int, db: Session):
    """
    Legger til et nytt skap med unik combi_id basert på romnavn og høyeste eksisterende nummer.
    """
    from backend.model.LockerRoom import LockerRoom
    locker_room = db.query(LockerRoom).filter_by(id=locker_room_id).first()
    if not locker_room:
        raise fastapi_error_handler("Garderoberom ikke funnet.", status_code=404)

    room_name = locker_room.name

    # Finn alle combi_id'er som starter med dette romnavnet
    existing_combis = db.query(Locker.combi_id).filter(
        Locker.locker_room_id == locker_room_id,
        Locker.combi_id.like(f"{room_name}-%")
    ).all()

    # Ekstraher tallene etter romnavnet, f.eks. "HU25-4" -> 4
    used_numbers = []
    for combi in existing_combis:
        try:
            suffix = int(combi[0].split("-")[-1])
            used_numbers.append(suffix)
        except:
            continue

    next_number = max(used_numbers) + 1 if used_numbers else 1
    combi_id = f"{room_name}-{next_number}"

    locker = Locker(locker_room_id=locker_room_id, status="Ledig", combi_id=combi_id)
    db.add(locker)
    db.commit()
    db.refresh(locker)

    return {
              f"message": "Skap {combi_id} ble opprettet i rom {room_name}.",
              "locker_id": Locker.id,
              f"combi_id": combi_id,
              "room_id": locker_room_id
            }


def add_multiple_lockers(locker_room_id: int, quantity: int, db: Session):
    """
    Legger til flere nye skap med unike combi_id-er som ikke eksisterer fra før.
    """
    if quantity <= 0:
        raise fastapi_error_handler("Antall skap må være større enn 0.", status_code=400)

    from backend.model.LockerRoom import LockerRoom
    locker_room = db.query(LockerRoom).filter_by(id=locker_room_id).first()
    if not locker_room:
        raise fastapi_error_handler("Garderoberom ikke funnet.", status_code=404)

    room_name = locker_room.name

    # Hent alle combi_id-er og finn hvilke tall som er brukt
    existing_combis = db.query(Locker.combi_id).filter(
        Locker.locker_room_id == locker_room_id,
        Locker.combi_id.like(f"{room_name}-%")
    ).all()

    used_numbers = set()
    for combi in existing_combis:
        try:
            suffix = int(combi[0].split("-")[-1])
            used_numbers.add(suffix)
        except ValueError:
            continue

    new_lockers = []
    current_number = 1
    lockers_created = 0

    # Fortsett å søke etter neste ledige nummer til vi har ønsket mengde skap
    while lockers_created < quantity:
        if current_number not in used_numbers:
            combi_id = f"{room_name}-{current_number}"
            locker = Locker(
                locker_room_id=locker_room_id,
                status="Ledig",
                combi_id=combi_id
            )
            new_lockers.append(locker)
            lockers_created += 1
        current_number += 1

    db.add_all(new_lockers)
    db.commit()

    for locker in new_lockers:
        db.refresh(locker)

    locker_details = [{
        "locker_id": locker.id,
        "combi_id": locker.combi_id,
        "status": locker.status
    } for locker in new_lockers]

    return {
        "message": f"{quantity} garderobeskap er opprettet i rom {locker_room_id}.",
        "multiple_locker_ids": locker_details
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


def remove_all_lockers_in_room(locker_room_id: int, db: Session):
    """
    Sletter alle garderobeskap knyttet til et spesifikt garderoberom.
    """
    from backend.model.LockerRoom import LockerRoom

    try:
        room = db.query(LockerRoom).filter_by(id=locker_room_id).first()
        if not room:
            raise fastapi_error_handler("Garderoberom ikke funnet.", status_code=404)

        deleted_count = db.query(Locker).filter_by(locker_room_id=locker_room_id).delete()
        db.commit()
        return {"message": f"{deleted_count} garderobeskap slettet fra rom '{room.name}'."}

    except Exception as e:
        db.rollback()
        raise fastapi_error_handler(f"Feil ved sletting av skap i rom: {str(e)}", status_code=500)
