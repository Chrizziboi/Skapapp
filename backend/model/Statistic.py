from sqlalchemy.orm import Session
from backend.model.Locker import Locker
from backend.model.StandardUser import StandardUser
from backend.model.LockerRoom import LockerRoom

class Statistic:
    """
    Klasse for å hente statistikk om garderobeskap og bruksmønstre.
    """

    @staticmethod
    def total_lockers(db: Session):
        """
        Henter totalt antall garderobeskap i systemet.
        """
        return db.query(Locker).count()

    @staticmethod
    def available_lockers(db: Session):
        """
        Henter totalt antall ledige garderobeskap.
        """
        return db.query(Locker).filter(Locker.status == "ledig").count()

    @staticmethod
    def occupied_lockers(db: Session):
        """
        Henter totalt antall opptatte garderobeskap.
        """
        return db.query(Locker).filter(Locker.status == "opptatt").count()

    @staticmethod
    def total_users(db: Session):
        """
        Henter totalt antall registrerte brukere.
        """
        return db.query(StandardUser).count()

    @staticmethod
    def lockers_by_room(db: Session):
        """
        Henter antall skap per garderoberom.
        """
        results = db.query(Locker.locker_room_id, LockerRoom.name, db.func.count(Locker.id))\
                    .join(LockerRoom, Locker.locker_room_id == LockerRoom.id)\
                    .group_by(Locker.locker_room_id, LockerRoom.name)\
                    .all()
        return [{"room_name": name, "locker_count": count} for _, name, count in results]

    @staticmethod
    def most_used_rooms(db: Session):
        """
        Henter garderoberommene med flest opptatte skap.
        """
        results = db.query(Locker.locker_room_id, LockerRoom.name, db.func.count(Locker.id))\
                    .join(LockerRoom, Locker.locker_room_id == LockerRoom.id)\
                    .filter(Locker.status == "opptatt")\
                    .group_by(Locker.locker_room_id, LockerRoom.name)\
                    .order_by(db.func.count(Locker.id).desc())\
                    .all()
        return [{"room_name": name, "occupied_count": count} for _, name, count in results]

    @staticmethod
    def most_active_users(db: Session):
        """
        Henter brukerne med flest reserveringer.
        """
        results = db.query(StandardUser.id, StandardUser.username, db.func.count(Locker.id))\
                    .join(Locker, StandardUser.id == Locker.user_id)\
                    .group_by(StandardUser.id, StandardUser.username)\
                    .order_by(db.func.count(Locker.id).desc())\
                    .all()
        return [{"username": username, "reservations": count} for _, username, count in results]
