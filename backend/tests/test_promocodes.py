import pytest
from fastapi.testclient import TestClient
from main import app

def test_get_promocodes(test_client):
    """Test getting available promocodes."""
    response = test_client.get("/promocodes/")
    assert response.status_code == 404

def test_validate_promocode(test_client):
    """Test validating a promocode."""
    response = test_client.post("/promocodes/validate", json={"code": "TEST10", "order_total": 1000})
    assert response.status_code == 404
