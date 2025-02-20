import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from main import api, Base, get_db

# Konfigurer testdatabasen
SQLALCHEMY_TESTDB_URL = "sqlite:///./database.db"
test_engine = create_engine(SQLALCHEMY_TESTDB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

# Opprett tabellene i testdatabasen
Base.metadata.create_all(bind=test_engine)

@pytest.fixture(scope="session")
def test_db():
    """Fixture for å gi en ny databaseøkt til hver test."""
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture(scope="session")
def client(test_db):
    """Fixture for å lage en testklient og bruke testdatabasen."""
    def override_get_db():
        yield test_db

    api.dependency_overrides[get_db] = override_get_db
    with TestClient(api) as c:
        yield c

# **Test for å opprette et garderoberom**
def test_create_locker_room(client):
    response = client.post("/locker_rooms/?name=TestRoom")
    assert response.status_code == 200, f"Feil ved opprettelse av garderoberom: {response.json()}"
    assert "room_id" in response.json()

# **Test for å opprette et garderobeskap**
def test_create_locker(client):
    response = client.post("/locker_rooms/?name=TestRoom")
    room_id = response.json()["room_id"]

    response = client.post(f"/lockers/?locker_room_id={room_id}")
    assert response.status_code == 200, f"Feil ved opprettelse av skap: {response.json()}"

    locker_id = response.json()["garderobeskaps_id"]
    response = client.get(f"/lockers/locker_id?locker_id={locker_id}")
    assert response.status_code == 200, f"Locker with ID {locker_id} not found!"

# **Test for å hente et garderobeskap**
def test_read_locker(client):
    response = client.post("/locker_rooms/?name=TestRoom")
    room_id = response.json()["room_id"]

    response = client.post(f"/lockers/?locker_room_id={room_id}")
    locker_id = response.json()["garderobeskaps_id"]

    response = client.get(f"/lockers/locker_id?locker_id={locker_id}")
    assert response.status_code == 200
    assert "locker_id" in response.json()
    assert "status" in response.json()
    assert response.json()["status"] == "Ledig"

# **Test for å legge til et notat på et garderobeskap**
def test_add_note_to_locker(client):
    response = client.post("/locker_rooms/?name=TestRoom")
    room_id = response.json()["room_id"]

    response = client.post(f"/lockers/?locker_room_id={room_id}")
    locker_id = response.json()["garderobeskaps_id"]

    response = client.put(f"/lockers/locker_id/note?locker_id={locker_id}&note=Testnotat")
    assert response.status_code == 200, f"Feil ved oppdatering av notat: {response.json()}"
    assert response.json()["note"] == "Testnotat"

# **Test for at et garderobeskap uten notat returnerer None eller tom string**
def test_read_locker_no_note(client):
    response = client.post("/locker_rooms/?name=TestRoom")
    room_id = response.json()["room_id"]

    response = client.post(f"/lockers/?locker_room_id={room_id}")
    locker_id = response.json()["garderobeskaps_id"]

    response = client.get(f"/lockers/locker_id?locker_id={locker_id}")
    assert response.status_code == 200
    assert "note" in response.json()
    assert response.json()["note"] is None or response.json()["note"] == ""

# **Test for at vi får en feilmelding hvis skapet ikke finnes**
def test_read_nonexistent_locker(client):
    response = client.get("/lockers/locker_id?locker_id=999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Skap ikke funnet"

# **Test for at vi får en feilmelding hvis vi prøver å legge til notat på et skap som ikke finnes**
def test_add_note_to_nonexistent_locker(client):
    response = client.put("/lockers/locker_id/note?locker_id=999&note=Test")
    assert response.status_code == 404
    assert response.json()["detail"] == "Locker not found"

@pytest.fixture(scope="function", autouse=True)
def cleanup(test_db):
    """Sletter alle data fra testdatabasen etter hver testkjøring."""
    yield  # Kjør testen først
    test_db.rollback()  # Rull tilbake eventuelle pågående transaksjoner
    for table in reversed(Base.metadata.sorted_tables):
        test_db.execute(table.delete())  # Slett alle rader i hver tabell
    test_db.commit()  # Bekreft slettingen