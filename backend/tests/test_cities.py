import pytest

def test_mock_city_creation(mock_city):
    """Test that mock city fixture works."""
    assert mock_city is not None
    assert mock_city.name == "Test City"
    assert mock_city.active == True

def test_mock_user_creation(mock_user_customer, mock_city):
    """Test that mock user fixture works."""
    assert mock_user_customer is not None
    assert mock_user_customer.phone_number.startswith("+9665")
    assert len(mock_user_customer.phone_number) == 13  # +966 + 8 digits
    assert mock_user_customer.role == "Customer"
    assert mock_user_customer.city_id == mock_city.id
