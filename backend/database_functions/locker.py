from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import Session
from database import Base

class Locker(Base):
    __tablename__ = "lockers"

    id = Column(Integer, primary_key=True, index=True)
    locker_id = Column(Integer, unique=True, index=True)
    status = Column(String, default="unlocked")
    is_active = Column(Boolean, default=True)


def locker_id():
    return Locker.locker_id


def add_locker(locker_id: int, status: str = "unlocked", is_active: bool = True, db: Session = None):
    """
    Legger til et nytt locker i databasen.

    Args:
        locker_id (int): Unik ID for skapet.
        status (str): Status for skapet (f.eks. 'unlocked', 'locked'). Default er 'unlocked'.
        is_active (bool): Om skapet er aktivt eller ikke. Default er True.
        db (Session): Databaseøkten.

    Returns:
        Locker: Det opprettede locker-objektet.
    """
    locker = Locker(locker_id=locker_id, status=status, is_active=is_active)
    db.add(locker)
    db.commit()
    db.refresh(locker)
    return locker
