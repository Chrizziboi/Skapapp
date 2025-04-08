from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import Session
from backend.Service.ErrorHandler import fastapi_error_handler
from database import Base
from passlib.context import CryptContext

# Passordkryptering
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)  # Hashed password
    role = Column(String, nullable=False)  # "admin" eller "user"

def create_admin(username: str, password: str, role: str, db: Session):
    """
    Oppretter en ny bruker med rolle (admin eller user).
    """
    existing_admin = db.query(AdminUser).filter(AdminUser.username == username).first()
    if existing_admin:
        raise fastapi_error_handler("Brukernavn finnes allerede.", status_code=400)

    hashed_password = pwd_context.hash(password)
    new_admin = AdminUser(username=username, password=hashed_password, role=role)
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)
    return new_admin

def get_admin_by_username(username: str, db: Session):
    """
    Henter en bruker basert på brukernavn.
    """
    return db.query(AdminUser).filter(AdminUser.username == username).first()

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

def authenticate_user(username: str, password: str, db: Session):
    """
    Autentiserer bruker med brukernavn og passord.
    """
    user = get_admin_by_username(username, db)
    if not user or not pwd_context.verify(password, user.password):
        return None
    return user
