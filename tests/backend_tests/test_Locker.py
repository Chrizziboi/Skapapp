import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.model.LockerRoom import LockerRoom
from database import Base
from backend.model.Locker import Locker, add_locker, add_multiple_lockers, add_note_to_locker, remove_locker


# Konfigurer testdatabase
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_add_locker(db):
    # Opprett locker room
    room = LockerRoom(name="HU24")
    db.add(room)
    db.commit()
    db.refresh(room)

    response = add_locker(room.id, db)
    assert response["combi_id"] == "HU24-1"
    assert response["room_id"] == room.id or "HU24" in response["message"]


def test_add_multiple_lockers(db):
    room = LockerRoom(name="HU30")
    db.add(room)
    db.commit()
    db.refresh(room)

    result = add_multiple_lockers(room.id, 3, db)
    assert result["message"] == f"3 garderobeskap er opprettet i rom {room.id}."
    assert len(result["multiple_locker_ids"]) == 3
    assert result["multiple_locker_ids"][0]["combi_id"] == "HU30-1"


def test_add_multiple_lockers_invalid_quantity(db):
    room = LockerRoom(name="HU50")
    db.add(room)
    db.commit()
    db.refresh(room)

    with pytest.raises(Exception) as exc_info:
        add_multiple_lockers(room.id, 0, db)
    assert "Antall skap må være større enn 0." in str(exc_info.value)


def test_add_note_to_locker(db):
    room = LockerRoom(name="HU60")
    db.add(room)
    db.commit()
    db.refresh(room)

    add_result = add_locker(room.id, db)
    locker_id = db.query(Locker).first().id

    updated = add_note_to_locker(locker_id, "Skap trenger rengjøring", db)
    assert updated.note == "Skap trenger rengjøring"


def test_add_note_to_nonexistent_locker(db):
    result = add_note_to_locker(999, "Noe tekst", db)
    assert result is None


def test_remove_locker(db):
    room = LockerRoom(name="HU70")
    db.add(room)
    db.commit()
    db.refresh(room)

    add_locker(room.id, db)
    locker_id = db.query(Locker).first().id
    response = remove_locker(locker_id, db)

    assert f"{locker_id}" in response["message"]


def test_remove_nonexistent_locker(db):
    response = remove_locker(999, db)
    assert response["error"] == "garderobeskap ikke funnet."
