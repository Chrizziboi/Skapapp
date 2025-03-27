import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.model.AdminUser import create_admin, get_admin_by_username, delete_admin
from database import Base


# Midlertidig testdatabase (SQLite i minne)
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    # Sett opp databasen
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_create_admin(db):
    admin = create_admin("testadmin", "securepass", False, db)
    assert admin.username == "testadmin"
    assert admin.is_superadmin is False
    assert admin.id is not None


def test_create_existing_admin_raises_error(db):
    create_admin("testadmin", "securepass", False, db)

    with pytest.raises(Exception) as exc_info:
        create_admin("testadmin", "anotherpass", True, db)

    assert "Brukernavn finnes allerede." in str(exc_info.value)


def test_get_admin_by_username(db):
    create_admin("someadmin", "pass", True, db)
    fetched = get_admin_by_username("someadmin", db)

    assert fetched is not None
    assert fetched.username == "someadmin"
    assert fetched.is_superadmin is True


def test_delete_admin(db):
    admin = create_admin("deleteuser", "pass", False, db)
    response = delete_admin(admin.id, db)

    assert "slettet" in response["message"]

    # Sjekk at adminen ikke lenger finnes
    assert get_admin_by_username("deleteuser", db) is None


def test_delete_nonexistent_admin_raises_error(db):
    with pytest.raises(Exception) as exc_info:
        delete_admin(999, db)

    assert "Administrator ikke funnet." in str(exc_info.value)
