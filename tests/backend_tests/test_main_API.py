import pytest
import requests

BASE_URL = "http://localhost:8080"

# Tester at API-et returnerer riktig melding for root-endepunktet, vil bare fungere under drift av app
# derfor er denne ignorert.
@pytest.skip
def test_read_root():
    response = requests.get(f"{BASE_URL}/")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello from Raspberry Pi and FastAPI!"}

# Tester at skapstatus returneres korrekt
"""def test_read_locker():
    response = requests.get(f"{BASE_URL}/lockers/123")
    assert response.status_code == 200
    assert response.json() == {"Skap_id": 123, "status": "låst"}"""
