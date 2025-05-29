import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base
from backend.model.Locker import *
from backend.model.LockerRoom import *
from backend.model.StandardUser import *
from backend.model.LockerLog import LockerLog as LockerLogModel
from backend.model.Statistic import *

# Oppsett for SQLite in-memory database
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="module")
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)

def test_statistic_functions(db):
    # Opprett rom
    room = LockerRoom(name="TestRom")
    db.add(room)
    db.commit()
    db.refresh(room)

    # Opprett brukere
    user1 = StandardUser(rfid_tag="AAA111")
    user2 = StandardUser(rfid_tag="BBB222")
    db.add_all([user1, user2])
    db.commit()

    # Opprett skap
    lockers = [
        Locker(id=1, locker_room_id=room.id, status="Ledig"),
        Locker(id=2, locker_room_id=room.id, status="Opptatt", note="Brukt"),
        Locker(id=3, locker_room_id=room.id, status="Ledig")
    ]
    db.add_all(lockers)
    db.commit()

    # Opprett loggdata
    logs = [
        LockerLogModel(locker_id=2, user_id=user1.id, action="Reservert"),
        LockerLogModel(locker_id=2, user_id=user1.id, action="Låst opp"),
        LockerLogModel(locker_id=1, user_id=user2.id, action="Låst opp")
    ]
    db.add_all(logs)
    db.commit()

    # === Tester og resultater ===
    print("🔍 Tester statistikkfunksjoner...")

    total = Statistic.total_lockers(db)
    print(f"✅ total_lockers(): {total}")
    assert total == 3

    occupied = Statistic.occupied_lockers(db)
    print(f"✅ occupied_lockers(): {occupied}")
    assert occupied == 1

    available = Statistic.available_lockers(locker_room_id=room.id, db=db)
    print(f"✅ available_lockers(): {available}")
    assert available["available_lockers"] == 2

    all_lockers = Statistic.all_lockers(db)
    print(f"✅ all_lockers(): Antall skap = {len(all_lockers)}")
    assert len(all_lockers) == 3

    total_users = Statistic.total_users(db)
    print(f"✅ total_users(): {total_users}")
    assert total_users == 2

    by_room = Statistic.lockers_by_room(db)
    print(f"✅ lockers_by_room(): {by_room}")
    assert by_room[0]["locker_count"] == 3

    available_by_room = Statistic.available_lockers_by_room(db)
    print(f"✅ available_lockers_by_room(): {available_by_room}")
    assert available_by_room[0]["available_lockers"] == 2

    most_used = Statistic.most_used_rooms(db)
    print(f"✅ most_used_rooms(): {most_used}")
    assert most_used[0]["occupied_count"] == 3

    most_active = Statistic.most_active_users(db)
    print(f"✅ most_active_users(): {most_active}")
    assert most_active[0]["username"] == "AAA111"
    assert most_active[0]["locker_count"] == 2
