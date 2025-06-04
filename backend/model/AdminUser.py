from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import Session
from backend.Service.ErrorHandler import fastapi_error_handler
from backend.model.Locker import Locker
from database import Base
from passlib.context import CryptContext

# Passordkryptering
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, index=True)
    password = Column(String, nullable=False)  # Hashed pin/passord
    role = Column(String, nullable=True)  # "admin" eller "user"

def create_admin(password: str, role: str, db: Session):
    """
    Oppretter en ny bruker basert på pin/passord og rolle.
    Forhindrer opprettelse dersom samme kode allerede finnes.
    """
    # Sjekk om passordet allerede er i bruk (ved å verifisere mot alle eksisterende brukere)
    users = db.query(AdminUser).all()
    for user in users:
        if pwd_context.verify(password, user.password):
            raise fastapi_error_handler("Denne koden er allerede i bruk.", status_code=400)

    # Hvis ikke, opprett ny bruker
    hashed_password = pwd_context.hash(password)
    new_admin = AdminUser(password=hashed_password, role=role)
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)
    return new_admin

def delete_admin(admin_id: int, db: Session):
    """
    Sletter en bruker basert på ID.
    """
    admin = db.query(AdminUser).filter(AdminUser.id == admin_id).first()
    if not admin:
        raise fastapi_error_handler("Bruker ikke funnet.", status_code=404)

    db.delete(admin)
    db.commit()
    return {"message": f"Bruker med ID {admin_id} er slettet."}

def authenticate_user(input_password: str, db: Session):
    """
    Autentiserer bruker kun basert på pin/passord.
    """
    users = db.query(AdminUser).all()
    for user in users:
        if pwd_context.verify(input_password, user.password):
            return user
    return None

def manual_release_locker(locker_id: int, db: Session):
    locker = db.query(Locker).filter(Locker.id == locker_id).first()
    if not locker:
        raise fastapi_error_handler(f"Ingen garderobeskap med id: {locker_id}", status_code=404)

    locker.status = "Ledig"
    locker.user_id = None
    db.commit()
    db.refresh(locker)

    from backend.model.LockerLog import log_action
    log_action(locker_id=locker.id, action="Manuelt frigjort", db=db)

    return {"message": f"Skap {locker.id} er manuelt frigjort av Admin."}