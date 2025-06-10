from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.model import LockerLog
from backend.model.Locker import Locker
from backend.model.StandardUser import StandardUser
from backend.model.LockerRoom import LockerRoom
from backend.Service.ErrorHandler import fastapi_error_handler

class Statistic:
    """
    Klasse for å hente statistikk om garderobeskap og bruksmønstre.
    """
    @staticmethod
    def get_all_rooms(db: Session):
        """
        Henter alle garderoberommene.
        """
        try:
            rooms = db.query(LockerRoom).all()
            return [{"room_id": room.id, "name": room.name} for room in rooms]
        except Exception as e:
            raise fastapi_error_handler(f"Feil ved henting av garderoberom: {str(e)}", status_code=500)

    @staticmethod
    def read_locker(locker_id: int, db: Session):
        """
        Endepunkt for å finne valgt garderobeskap.
        """
        try:
            locker = db.query(Locker).filter(Locker.id == locker_id).first()
            if locker is None:
                raise fastapi_error_handler("Garderobeskap ikke funnet.", status_code=404)
            return {"locker_id": locker.id, "status": locker.status, "note": locker.note}
        except Exception as e:
            raise fastapi_error_handler(f"Feil ved henting av garderobeskap: {str(e)}", status_code=500)

    @staticmethod
    def total_lockers(db: Session):
        return db.query(Locker).count()

    @staticmethod
    def available_lockers(locker_room_id: int, db: Session):
        """
        Endepunkt for å hente antall ledige skap i et spesifikt garderoberom.
        """
        try:
            available_lockers = db.query(Locker).filter(
                Locker.locker_room_id == locker_room_id,
                Locker.status.ilike("Ledig")
            ).count()

            return {"locker_room_id": locker_room_id, "available_lockers": available_lockers}
        except Exception as e:
            raise fastapi_error_handler(f"Feil ved henting av garderobeskap: {str(e)}", status_code=500)

    @staticmethod
    def all_lockers(db: Session):
        """
        Endepunkt for å hente ALLE skap.
        """
        try:
            lockers = db.query(Locker).all()
            return [
                {
                    "locker_id": locker.id,
                    "combi_id": locker.combi_id,
                    "locker_room_id": locker.locker_room_id,  # Legger til rom-ID
                    "status": locker.status,
                    "note": locker.note if locker.note else "N/A"  # Hvis notat er None, sett "N/A"
                }
                for locker in lockers
            ]
        except Exception as e:
            raise fastapi_error_handler(f"Feil ved henting av garderoberom: {str(e)}", status_code=500)

    @staticmethod
    def occupied_lockers(db: Session):
        return db.query(Locker).filter(Locker.status == "Opptatt").count()

    @staticmethod
    def total_users(db: Session):
        return db.query(StandardUser).count()

    @staticmethod
    def lockers_by_room(db: Session):

        results = db.query(
            Locker.locker_room_id,
            LockerRoom.name,
            func.count(Locker.id)
        ).join(LockerRoom, Locker.locker_room_id == LockerRoom.id)\
         .group_by(Locker.locker_room_id, LockerRoom.name)\
         .all()
        return [{"room_name": name, "locker_count": count} for _, name, count in results]

    @staticmethod
    def available_lockers_by_room(db: Session):
        """
        Returnerer antall ledige skap per garderoberom.
        """
        results = db.query(
            Locker.locker_room_id,
            LockerRoom.name,
            func.count(Locker.id)
        ).join(
            LockerRoom, Locker.locker_room_id == LockerRoom.id
        ).filter(
            Locker.status == "Ledig"
        ).group_by(
            Locker.locker_room_id, LockerRoom.name
        ).all()
        return [{"room_name": name, "available_lockers": count} for _, name, count in results]

    @staticmethod
    def most_used_rooms(db: Session):
        results = db.query(
            LockerRoom.name,
            func.count(LockerLog.id)
        ).join(
            Locker, LockerRoom.id == Locker.locker_room_id
        ).join(
            LockerLog, Locker.id == LockerLog.locker_id
        ).filter(
            LockerLog.action.in_(["Reservert", "Låst opp"])
        ).group_by(
            LockerRoom.name
        ).order_by(
            func.count(LockerLog.id).desc()
        ).all()

        return [{"room_name": name, "usage_count": count} for name, count in results]

    @staticmethod
    def most_active_users(db: Session):
        results = db.query(
            StandardUser.id,
            StandardUser.rfid_tag,
            func.count(LockerLog.id)
        ).join(
            LockerLog, StandardUser.id == LockerLog.user_id
        ).group_by(
            StandardUser.id, StandardUser.rfid_tag
        ).order_by(
            func.count(LockerLog.id).desc()
        ).all()

        return [{"user_id": uid, "rfid_tag": tag, "usage_count": count} for uid, tag, count in results]

    @staticmethod
    def raspberry_occupied_locker(db: Session):
        lockers = db.query(Locker).filter(Locker.status == "Opptatt").all()
        return [
            {
                "locker_id": locker.id
            }
            for locker in lockers
        ]


