from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import Session
from datetime import datetime
from database import Base

class LockerLog(Base):
    __tablename__ = "locker_logs"

    id = Column(Integer, primary_key=True, index=True)
    locker_id = Column(Integer, ForeignKey("lockers.id"))
    user_id = Column(Integer, ForeignKey("standard_users.id"))
    action = Column(String)  # "Låst opp" eller "lock"
    timestamp = Column(DateTime, default=datetime.utcnow)

def log_unlock_action(locker_id: int, user_id: int, db: Session):
    """
    Logger en unlock-hendelse.
    """
    new_log = LockerLog(
        locker_id=locker_id,
        user_id=user_id,
        action="Låst opp",
        timestamp=datetime.utcnow()
    )
    db.add(new_log)
    db.commit()
    db.refresh(new_log)
    return new_log

