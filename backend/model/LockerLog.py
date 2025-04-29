from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import Session
from datetime import datetime as dt, UTC, timedelta

from backend.model.Locker import Locker
from database import Base

class LockerLog(Base):
    __tablename__ = "locker_logs"

    id = Column(Integer, primary_key=True, index=True)
    locker_id = Column(Integer, ForeignKey("lockers.id"))
    user_id = Column(Integer, ForeignKey("standard_users.id"))
    action = Column(String)  # "Låst opp" eller "Låst"
    timestamp = Column(DateTime, default=dt.now(UTC))

def log_unlock_action(locker_id: int, user_id: int, db: Session):
    """
    Logger en unlock-hendelse.
    """
    new_log = LockerLog(
        locker_id=locker_id,
        user_id=user_id,
        action="Låst opp",
        timestamp=dt.now(UTC)
    )
    db.add(new_log)
    db.commit()
    db.refresh(new_log)
    return new_log


def release_expired_lockers_logic(db: Session) -> list[str]:
    """
    Frigjør skap som har vært reservert i over 15 timer, og logger det som 'Automatisk frigjort'.
    Returnerer en liste med combi_id-er for de frigjorte skapene.
    """
    released = []
    expiration_time = dt.now(UTC) - timedelta(seconds=15)  # Bytt til hours=15 senere

    occupied_lockers = db.query(Locker).filter(Locker.status.ilike("Opptatt")).all()

    for locker in occupied_lockers:
        last_reservation = db.query(LockerLog).filter(
            LockerLog.locker_id == locker.id,
            LockerLog.action == "Opptatt"
        ).order_by(LockerLog.timestamp.desc()).first()

        if last_reservation:
            # Håndter naive timestamps uten tzinfo
            ts = last_reservation.timestamp
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)

            if ts < expiration_time:
                locker.status = "Ledig"
                locker.user_id = None
                db.commit()
                db.refresh(locker)

                new_log = LockerLog(
                    locker_id=locker.id,
                    user_id=None,
                    action="Automatisk frigjort",
                    timestamp=dt.now(UTC).replace(microsecond=0)
                )
                db.add(new_log)
                db.commit()

                released.append(locker.combi_id)

    return released
