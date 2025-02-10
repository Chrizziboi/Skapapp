from sqlalchemy import Column, Integer, String, Boolean
from database import Base

class Locker(Base):
    __tablename__ = "lockers"

    id = Column(Integer, primary_key=True, index=True)
    locker_id = Column(Integer, unique=True, index=True)
    status = Column(String, default="unlocked")
    is_active = Column(Boolean, default=True)
