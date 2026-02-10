import pytest
from fastapi.testclient import TestClient
from main import app

def test_get_payments(test_client):
    """Test getting user payments."""
    response = test_client.get("/payments/")
    assert response.status_code == 405

def test_create_payment(test_client):
    """Test creating a payment."""
    response = test_client.post("/payments/", json={"invoice_id": 1, "amount": 100})
    assert response.status_code == 403
