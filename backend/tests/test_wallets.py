import pytest
from fastapi.testclient import TestClient
from main import app

def test_get_wallet(test_client):
    """Test getting user wallet."""
    response = test_client.get("/wallets/")
    assert response.status_code == 404

def test_update_wallet(test_client):
    """Test updating wallet balance."""
    response = test_client.put("/wallets/", json={"balance": 1000})
    assert response.status_code == 404
