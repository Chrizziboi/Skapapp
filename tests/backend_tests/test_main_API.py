import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from main import api, Base, get_db

# Konfigurasjon av testdatabasen
SQLALCHEMY_TESTDB_URL = "sqlite:///./database.db" # SQLite-database for testing
test_engine = create_engine(SQLALCHEMY_TESTDB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest.fixture(scope="function")
def test_db():
    """Fixture for å gi en ny databaseøkt til hver test."""
    Base.metadata.create_all(bind=test_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)

@pytest.fixture(scope="function")
def client(test_db):
    """Fixture for å lage en testklient og bruke testdatabasen."""
    def override_get_db():
        yield test_db

    api.dependency_overrides[get_db] = override_get_db
    with TestClient(api) as c:
        yield c


# Test for å opprette et nytt garderoberom
def test_create_room(client):
    response = client.post("/locker_rooms/?name=TestRom")
    assert response.status_code == 200
    assert response.json() == {
        "message": "Garderoberom opprettet",
        "navn": "TestRom"
    }

# Test for å lage et nytt garderobeskap
def test_create_locker(client):
    response = client.post("/lockers/?locker_room_id=1")
    assert response.status_code == 200
    assert response.json() == {
        "message": "Garderobeskap Opprettet",
        "garderobeskaps_id": 1
    }

@pytest.fixture(scope="session", autouse=True)
def cleanup():
    yield  # Vent til alle testene er fullført
    Base.metadata.drop_all(bind=test_engine)
