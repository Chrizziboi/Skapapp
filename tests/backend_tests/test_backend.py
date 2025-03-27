import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.model.AdminUser import create_admin, get_admin_by_username, delete_admin
from backend.model.StandardUser import create_standard_user, get_user_by_rfid_tag, reserve_locker
from backend.model.LockerRoom import create_locker_room, delete_locker_room
from backend.model.Locker import add_locker, add_multiple_lockers, add_note_to_locker, remove_locker
from backend.model.Statistic import Statistic
from database import Base

os.makedirs("tests/backend_tests", exist_ok=True)

# Koble til riktig testdatabase
TEST_DB_PATH = "tests/backend_tests/database.db"
TEST_DB_URL = f"sqlite:///{TEST_DB_PATH}"


if os.path.exists(TEST_DB_PATH):
    os.remove(TEST_DB_PATH)

test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(bind=test_engine)

@pytest.fixture(scope="function")
def db():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_admin_user(db):
    admin = create_admin("admin", "pass", True, db)
    assert admin.username == "admin"
    fetched = get_admin_by_username("admin", db)
    assert fetched is not None
    response = delete_admin(admin.id, db)
    assert "slettet" in response["message"]


def test_create_locker_room(db):
    room = create_locker_room("TestRom", db)
    assert room["name"] == "TestRom"
    locker = add_locker(room["room_id"], db)
    room_name = db.query(create_locker_room.__globals__['LockerRoom']).filter_by(id=room["room_id"]).first().name
    assert room_name in locker["combi_id"]

    multiple = add_multiple_lockers(room["room_id"], 2, db)
    assert len(multiple["multiple_locker_ids"]) == 2

    locker_id = multiple["multiple_locker_ids"][0]["locker_id"]
    updated = add_note_to_locker(locker_id, "Note", db)
    assert updated.note == "Note"

    removed = remove_locker(locker_id, db)
    assert "slettet" in removed["message"]

# -----------------------------------------------
# LockerRoom tester
# -----------------------------------------------

def test_create_locker_room_success(db):
    result = create_locker_room("TestRomA", db)
    assert result["name"] == "TestRomA"
    assert "opprettet" in result["message"]

def test_delete_locker_room_success(db):
    room = create_locker_room("TestRomB", db)
    response = delete_locker_room(room["room_id"], db)
    assert "slettet" in response["message"]

def test_locker_room_deletion(db):
    room = create_locker_room("DelRoom", db)
    add_multiple_lockers(room["room_id"], 2, db)
    response = delete_locker_room(room["room_id"], db)
    assert "slettet" in response["message"]
# -----------------------------------------------
# Locker tester
# -----------------------------------------------

def test_second_add_locker_success(db):
    room = create_locker_room("SkapRom1", db)
    locker = add_locker(room["room_id"], db)
    assert locker["combi_id"].startswith("SkapRom1-")
    assert locker["room_id"] == room["room_id"]

def test_add_multiple_lockers_success(db):
    room = create_locker_room("SkapRom2", db)
    result = add_multiple_lockers(room["room_id"], 4, db)
    assert len(result["multiple_locker_ids"]) == 4
    assert result["message"].startswith("4 garderobeskap")

def test_add_note_to_locker_success(db):
    room = create_locker_room("SkapRom3", db)
    locker = add_locker(room["room_id"], db)
    updated = add_note_to_locker(locker["locker_id"], "Defekt lås", db)
    assert updated.note == "Defekt lås"

def test_remove_locker_success(db):
    room = create_locker_room("SkapRom4", db)
    locker = add_locker(room["room_id"], db)
    response = remove_locker(locker["locker_id"], db)
    assert "slettet" in response["message"]

@pytest.mark.skip
def test_standard_user_and_reservation(db):
    user = create_standard_user("RFID1", db)
    assert user.rfid_tag == "RFID1"
    assert get_user_by_rfid_tag("RFID1", db) is not None

    room = create_locker_room("TestRoom", db)
    add_multiple_lockers(room["room_id"], 3, db)
    res = reserve_locker(user.id, room["room_id"], db)
    assert "reservert for bruker" in res["message"]

@pytest.mark.skip
def test_statistics(db):
    room = create_locker_room("StatRoom", db)
    user = create_standard_user("RFID2", db)
    add_multiple_lockers(room["room_id"], 2, db)
    reserve_locker(user.id, room["room_id"], db)

    assert Statistic.total_lockers(db) == 2
    assert Statistic.total_users(db) == 1
    assert isinstance(Statistic.lockers_by_room(db), list)
    assert isinstance(Statistic.all_lockers(db), list)
    assert isinstance(Statistic.most_used_rooms(db), list)
    assert isinstance(Statistic.available_lockers_by_room(db), list)
    assert isinstance(Statistic.most_active_users(db), list)

# -----------------------------------------------
# Edge LockerRoom tester
# -----------------------------------------------

def test_create_duplicate_locker_room(db):
    create_locker_room("DuplikatRom", db)
    with pytest.raises(Exception) as e:
        create_locker_room("DuplikatRom", db)
    assert "finnes allerede" in str(e.value)

def test_delete_nonexistent_locker_room(db):
    with pytest.raises(Exception) as e:
        delete_locker_room(999, db)
    assert "ikke funnet" in str(e.value)

# -----------------------------------------------
# Edge Locker tester
# -----------------------------------------------

def test_add_locker_to_nonexistent_room(db):
    with pytest.raises(Exception) as e:
        add_locker(999, db)
    assert "Garderoberom ikke funnet" in str(e.value)

def test_add_multiple_lockers_zero_quantity(db):
    room = create_locker_room("EmptyRoom", db)
    with pytest.raises(Exception) as e:
        add_multiple_lockers(room["room_id"], 0, db)
    assert "må være større enn 0" in str(e.value)

def test_add_note_to_nonexistent_locker(db):
    result = add_note_to_locker(999, "Ukjent skap", db)
    assert result is None

def test_remove_nonexistent_locker(db):
    result = remove_locker(999, db)
    assert result["error"] == "garderobeskap ikke funnet."

def test_note_after_room_deletion(db):
    room = create_locker_room("TempRoom", db)
    locker = add_locker(room["room_id"], db)
    delete_locker_room(room["room_id"], db)
    result = add_note_to_locker(locker["locker_id"], "Etter sletting", db)
    assert result is None  # fordi skapet skal være slettet



