from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import Session
from backend.Service.ErrorHandler import fastapi_error_handler
from database import Base
from passlib.context import CryptContext
from backend.auth.auth_handler import verify_password


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
    if not password or not role:
        raise fastapi_error_handler("Både passord og rolle må oppgis.", status_code=400)

    # Sjekk om passordet allerede finnes (samme PIN skal ikke gjenbrukes)
    users = db.query(AdminUser).all()
    for user in users:
        if pwd_context.verify(password, user.password):
            raise fastapi_error_handler("Denne koden er allerede i bruk.", status_code=400)

    # Opprett bruker
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

def authenticate_user(password: str, db):
    users = db.query(AdminUser).all()
    for user in users:
        if verify_password(password, user.password):
            return user
    return None

