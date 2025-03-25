from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.model.Locker import Locker
from backend.model.StandardUser import StandardUser
from backend.model.LockerRoom import LockerRoom

class Statistic:
    """
    Klasse for å hente statistikk om garderobeskap og bruksmønstre.
    """

    @staticmethod
    def total_lockers(db: Session):
        return db.query(Locker).count()

    @staticmethod
    def available_lockers(db: Session):
        return db.query(Locker).filter(Locker.status.ilike("ledig")).count()

    @staticmethod
    def occupied_lockers(db: Session):
        return db.query(Locker).filter(Locker.status.ilike("opptatt")).count()

    @staticmethod
    def total_users(db: Session):
        return db.query(StandardUser).count()

    @staticmethod
    def lockers_by_room(db: Session):
        rooms = db.query(LockerRoom).all()
        result = []
        for room in rooms:
            total = db.query(Locker).filter(Locker.locker_room_id == room.id).count()
            ledige = db.query(Locker).filter(Locker.locker_room_id == room.id, Locker.status.ilike("ledig")).count()
            opptatt = db.query(Locker).filter(Locker.locker_room_id == room.id, Locker.status.ilike("opptatt")).count()
            result.append({
                "room_name": room.name,
                "locker_count": total,
                "available": ledige,
                "occupied": opptatt
            })
        return result

    @staticmethod
    def most_used_rooms(db: Session):
        results = db.query(Locker.locker_room_id, LockerRoom.name, func.count(Locker.id))\
                    .join(LockerRoom, Locker.locker_room_id == LockerRoom.id)\
                    .filter(Locker.status == "opptatt")\
                    .group_by(Locker.locker_room_id, LockerRoom.name)\
                    .order_by(func.count(Locker.id).desc())\
                    .all()
        return [{"room_name": name, "occupied_count": count} for _, name, count in results]

    @staticmethod
    def most_active_users(db: Session):
        results = db.query(StandardUser.id, StandardUser.username, func.count(Locker.id)) \
            .join(Locker, StandardUser.id == Locker.user_id, isouter=True) \
            .group_by(StandardUser.id, StandardUser.username) \
            .order_by(func.count(Locker.id).desc()) \
            .all()
        return [{"username": username, "reservations": count} for _, username, count in results]

