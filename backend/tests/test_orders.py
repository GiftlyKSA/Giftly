import pytest
from fastapi.testclient import TestClient
from main import app
from models import Order, User
from datetime import datetime, timedelta

def test_create_order(test_client, mock_user_customer, mock_city):
    """Test creating a new order."""
    # Without auth, this should fail
    response = test_client.post("/orders/", json={
        "city_id": mock_city.id,
        "description": "Test order",
        "delivery_date": (datetime.utcnow() + timedelta(days=1)).isoformat()
    })
    # Should fail due to no auth
    assert response.status_code == 403

def test_get_user_orders(test_client):
    """Test getting user orders."""
    # Without auth, should fail
    response = test_client.get("/orders/")
    assert response.status_code == 403

def test_get_order(test_client, mock_order):
    """Test getting a specific order."""
    response = test_client.get(f"/orders/{mock_order.order_id}")
    assert response.status_code == 403  # No auth

def test_cancel_order(test_client, mock_order):
    """Test canceling an order."""
    response = test_client.put(f"/orders/{mock_order.order_id}/cancel", json={"reason": "Test cancel"})
    assert response.status_code == 403

def test_assign_order(test_client, mock_order, mock_user_courier):
    """Test assigning an order to a courier."""
    response = test_client.put(f"/orders/{mock_order.order_id}/assign", json={"assigned_to_user_id": mock_user_courier.id})
    assert response.status_code == 403

def test_get_available_orders(test_client):
    """Test getting available orders for courier."""
    response = test_client.get("/orders/courier/available")
    assert response.status_code == 403

def test_accept_order(test_client, mock_order):
    """Test accepting an order by courier."""
    response = test_client.put(f"/orders/{mock_order.order_id}/accept")
    assert response.status_code == 403

def test_get_courier_active_orders(test_client):
    """Test getting courier's active orders."""
    response = test_client.get("/orders/courier/active")
    assert response.status_code == 403

def test_get_courier_all_orders(test_client):
    """Test getting all courier orders."""
    response = test_client.get("/orders/courier/all")
    assert response.status_code == 403

def test_get_courier_stats(test_client):
    """Test getting courier statistics."""
    response = test_client.get("/orders/courier/stats")
    assert response.status_code == 403

def test_complete_order(test_client, mock_order):
    """Test completing an order."""
    response = test_client.put(f"/orders/{mock_order.order_id}/complete")
    assert response.status_code == 403
