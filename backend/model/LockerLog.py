from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import Session
from datetime import datetime as dt, UTC, timedelta

from backend.model.Locker import Locker
from database import Base
from backend.websocket_broadcast import broadcast_message

class LockerLog(Base):
    __tablename__ = "locker_logs"

    id = Column(Integer, primary_key=True, index=True)
    locker_id = Column(Integer, ForeignKey("lockers.id"))
    user_id = Column(Integer, ForeignKey("standard_users.id"))
    action = Column(String)  # "Låst opp", "Låst" eller "Automatisk frigjort"
    timestamp = Column(DateTime, default=dt.now(UTC))

async def log_action(locker_id: int, user_id: int | None, action: str, db: Session):
    log = LockerLog(locker_id=locker_id, user_id=user_id, action=action, timestamp=dt.now(UTC))
    db.add(log)
    db.commit()
    db.refresh(log)
    await broadcast_message("update")
    return log  # vurder dette, som i de andre funksjonene

async def log_unlock_action(locker_id: int, user_id: int, db: Session):
    """
    Logger en Låst opp-hendelse.
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
    await broadcast_message("update")
    return new_log


async def log_lock_action(locker_id: int, user_id: int, db: Session):
    """
    Logger en Låst-hendelse.
    """
    new_log = LockerLog(
        locker_id=locker_id,
        user_id=user_id,
        action="Låst",
        timestamp=dt.now(UTC)
    )
    db.add(new_log)
    db.commit()
    db.refresh(new_log)
    await broadcast_message("update")
    return new_log


async def log_reserved_action(locker_id: int, user_id: int, db: Session):
    """
    Logger en reserverings-hendelse.
    """
    new_log = LockerLog(
        locker_id=locker_id,
        user_id=user_id,
        action="Reservert",
        timestamp=dt.now(UTC)
    )
    db.add(new_log)
    db.commit()
    db.refresh(new_log)
    await broadcast_message("update")
    return new_log


async def release_expired_lockers_logic(db: Session) -> list[str]:
    """
    Frigjør skap som har vært 'Reservert' i over 15 timer.
    """
    released = []
    expiration_time = dt.now(UTC) - timedelta(hours=15)  # evt. seconds=15 for testing

    occupied_lockers = db.query(Locker).filter(Locker.status.ilike("Opptatt")).all()
    print(f"[Automatisk Skapopplåser] Fant {len(occupied_lockers)} opptatte skap")

    for locker in occupied_lockers:
        last_reservation = db.query(LockerLog).filter(
            LockerLog.locker_id == locker.id,
            LockerLog.action == "Reservert"
        ).order_by(LockerLog.timestamp.desc()).first()

        if not last_reservation:
            print(f"[Automatisk Skapopplåser] Skap {locker.combi_id} har aldri blitt reservert – hopper over")
            continue

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
            print(f"[Automatisk Skapopplåser] Frigjorde skap: {locker.combi_id}")

    if released:
        await broadcast_message("update")

    return released
