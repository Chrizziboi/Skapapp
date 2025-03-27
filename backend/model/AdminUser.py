from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import Session

from backend.Service.ErrorHandler import fastapi_error_handler
from database import Base


class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)  # Bør hashes før lagring
    is_superadmin = Column(Boolean, default=False)

def create_admin(username: str, password: str, is_superadmin: bool, db: Session):
    """
    Oppretter en ny administratorbruker.
    """
    existing_admin = db.query(AdminUser).filter(AdminUser.username == username).first()
    if existing_admin:
        raise fastapi_error_handler("Brukernavn finnes allerede.", status_code=400)

    new_admin = AdminUser(username=username, password=password, is_superadmin=is_superadmin)
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)
    return new_admin

def get_admin_by_username(username: str, db: Session):
    """
    Henter en administratorbruker basert på brukernavn.
    """
    return db.query(AdminUser).filter(AdminUser.username == username).first()

def delete_admin(admin_id: int, db: Session):
    """
    Sletter en administratorbruker.
    """
    admin = db.query(AdminUser).filter(AdminUser.id == admin_id).first()
    if not admin:
        raise fastapi_error_handler("Administrator ikke funnet.", status_code=404)

    db.delete(admin)
    db.commit()
    return {"message": f"Administrator med ID {admin_id} er slettet."}
