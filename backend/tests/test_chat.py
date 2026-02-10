import pytest
from fastapi.testclient import TestClient
from main import app

def test_get_conversations(test_client):
    """Test getting user conversations."""
    response = test_client.get("/chat/conversations")
    assert response.status_code == 403

def test_get_messages(test_client, mock_conversation):
    """Test getting messages for a conversation."""
    response = test_client.get(f"/chat/conversations/{mock_conversation.id}/messages")
    assert response.status_code == 403
