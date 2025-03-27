from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.model.Locker import Locker
from backend.model.StandardUser import StandardUser
from backend.model.LockerRoom import LockerRoom
from backend.Service.ErrorHandler import fastapi_error_handler

class Statistic:
    """
    Klasse for å hente statistikk om garderobeskap og bruksmønstre.
    """
    def get_all_rooms(db: Session):
        """
        Henter alle garderoberommene.
        """
        try:
            rooms = db.query(LockerRoom).all()
            return [{"room_id": room.id, "name": room.name} for room in rooms]
        except Exception as e:
            return fastapi_error_handler(f"Feil ved henting av garderoberom: {str(e)}", status_code=500)


    def read_locker(locker_id: int, db: Session):
        """
        Endepunkt for å finne valgt garderobeskap.
        """
        try:
            locker = db.query(Locker).filter(Locker.id == locker_id).first()
            if locker is None:
                raise fastapi_error_handler(status_code=404, detail="Garderobeskap ikke funnet.")
            return {"locker_id": locker.id, "status": locker.status, "note": locker.note}
        except Exception as e:
            return fastapi_error_handler(f"Feil ved henting av garderobeskap: {str(e)}", status_code=500)

    def total_lockers(db: Session):
        return db.query(Locker).count()


    def available_lockers(locker_room_id: int, db: Session):
        """
        Endepunkt for å hente antall ledige skap i et spesifikt garderoberom.
        """
        available_lockers = db.query(Locker).filter(
            Locker.locker_room_id == locker_room_id,
            Locker.status.ilike("Ledig")
        ).count()
        try:
            return {"locker_room_id": locker_room_id, "available_lockers": available_lockers}
        except Exception as e:
            return fastapi_error_handler(f"Feil ved henting av garderobeskap: {str(e)}", status_code=500)

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
            return fastapi_error_handler(f"Feil ved henting av garderoberom: {str(e)}", status_code=500)

    def occupied_lockers(db: Session):
        return db.query(Locker).filter(Locker.status == "Opptatt").count()



    def total_users(db: Session):
        return db.query(StandardUser).count()


    def lockers_by_room(db: Session):

        results = db.query(
            Locker.locker_room_id,
            LockerRoom.name,
            func.count(Locker.id)
        ).join(LockerRoom, Locker.locker_room_id == LockerRoom.id)\
         .group_by(Locker.locker_room_id, LockerRoom.name)\
         .all()
        return [{"room_name": name, "locker_count": count} for _, name, count in results]


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
            Locker.status == "ledig"
        ).group_by(
            Locker.locker_room_id, LockerRoom.name
        ).all()
        return [{"room_name": name, "available_lockers": count} for _, name, count in results]


    def most_used_rooms(db: Session):
        results = db.query(
            Locker.locker_room_id,
            LockerRoom.name,
            func.count(Locker.id)
        ).join(
            LockerRoom, Locker.locker_room_id == LockerRoom.id
        ).filter(
            Locker.status == "opptatt"
        ).group_by(
            Locker.locker_room_id, LockerRoom.name
        ).order_by(
            func.count(Locker.id).desc()
        ).all()


        return [{"room_name": name, "occupied_count": count} for _, name, count in results]


    def most_active_users(db: Session):

        results = db.query(
            StandardUser.id,
            StandardUser.username,
            func.count(Locker.id)
        ).join(
            Locker, StandardUser.id == Locker.user_id
        ).group_by(
            StandardUser.id, StandardUser.username
        ).order_by(
            func.count(Locker.id).desc()
        ).all()

        results = db.query(StandardUser.id, StandardUser.username, func.count(Locker.id)) \
            .join(Locker, StandardUser.id == Locker.user_id, isouter=True) \
            .group_by(StandardUser.id, StandardUser.username) \
            .order_by(func.count(Locker.id).desc()) \
            .all()


