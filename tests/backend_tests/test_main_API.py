import pytest
import os
from fastapi.testclient import TestClient
from main import Jinja2Templates
from main import api

static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

client = TestClient(api)


def test_main_page_loads():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_admin_page_loads():
    response = client.get("/admin_page")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_standard_user_page_loads():
    response = client.get("/available_lockers")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_admin_wardrobe_management_page_loads():
    response = client.get("/admin_wardrobe")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
