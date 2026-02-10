import pytest
from fastapi.testclient import TestClient
from main import app

def test_get_user_invoices(test_client):
    """Test getting user invoices."""
    response = test_client.get("/invoices/")
    assert response.status_code == 405

def test_get_invoice(test_client):
    """Test getting a specific invoice."""
    response = test_client.get("/invoices/INV-001")
    assert response.status_code == 404

def test_create_invoice(test_client):
    """Test creating an invoice."""
    response = test_client.post("/invoices/", json={"order_id": 1})
    assert response.status_code == 422
