from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.model.LockerLog import LockerLog as LockerLogModel
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
        try:
            rooms = db.query(LockerRoom).all()
            return [{"room_id": room.id, "name": room.name} for room in rooms]
        except Exception as e:
            raise fastapi_error_handler(f"Feil ved henting av garderoberom: {str(e)}", status_code=500)

    @staticmethod
    def read_locker(locker_id: int, db: Session):
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
    def occupied_lockers(db: Session):
        return db.query(Locker).filter(Locker.status.ilike("Opptatt")).count()

    @staticmethod
    def available_lockers(locker_room_id: int, db: Session):
        try:
            count = db.query(Locker).filter(
                Locker.locker_room_id == locker_room_id,
                Locker.status.ilike("Ledig")
            ).count()
            return {"locker_room_id": locker_room_id, "available_lockers": count}
        except Exception as e:
            raise fastapi_error_handler(f"Feil ved henting av ledige skap: {str(e)}", status_code=500)

    @staticmethod
    def all_lockers(db: Session):
        try:
            lockers = db.query(Locker).all()
            return [
                {
                    "locker_id": locker.id,
                    "locker_room_id": locker.locker_room_id,
                    "status": locker.status,
                    "note": locker.note if locker.note else "N/A"
                }
                for locker in lockers
            ]
        except Exception as e:
            raise fastapi_error_handler(f"Feil ved henting av alle skap: {str(e)}", status_code=500)

    @staticmethod
    def total_users(db: Session):
        return db.query(StandardUser).count()

    @staticmethod
    def lockers_by_room(db: Session):
        all_rooms = db.query(LockerRoom).all()
        result = []
        for room in all_rooms:
            total = db.query(Locker).filter(Locker.locker_room_id == room.id).count()
            available = db.query(Locker).filter(Locker.locker_room_id == room.id, Locker.status.ilike("Ledig")).count()
            occupied = db.query(Locker).filter(Locker.locker_room_id == room.id, Locker.status.ilike("Opptatt")).count()
            result.append({
                "room_name": room.name,
                "locker_count": total,
                "available": available,
                "occupied": occupied
            })
        return result

    @staticmethod
    def available_lockers_by_room(db: Session):
        results = db.query(
            Locker.locker_room_id,
            LockerRoom.name,
            func.count(Locker.id)
        ).join(LockerRoom, Locker.locker_room_id == LockerRoom.id)\
         .filter(Locker.status.ilike("Ledig"))\
         .group_by(Locker.locker_room_id, LockerRoom.name).all()
        return [{"room_name": name, "available_lockers": count} for _, name, count in results]

    @staticmethod
    def most_used_rooms(db: Session):
        results = db.query(
            LockerRoom.name,
            func.count(LockerLogModel.id)
        ).join(Locker, LockerRoom.id == Locker.locker_room_id)\
         .join(LockerLogModel, Locker.id == LockerLogModel.locker_id)\
         .filter(LockerLogModel.action.in_(["Reservert", "Låst opp"]))\
         .group_by(LockerRoom.name)\
         .order_by(func.count(LockerLogModel.id).desc()).all()
        return [{"room_name": name, "occupied_count": count} for name, count in results]

    @staticmethod
    def most_active_users(db: Session):
        results = db.query(
            StandardUser.id,
            StandardUser.rfid_tag,
            func.count(LockerLogModel.id)
        ).join(LockerLogModel, StandardUser.id == LockerLogModel.user_id)\
         .group_by(StandardUser.id, StandardUser.rfid_tag)\
         .order_by(func.count(LockerLogModel.id).desc()).all()
        return [{"username": tag, "locker_count": count} for _, tag, count in results]


