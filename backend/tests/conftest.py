import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(__file__) + '/..')

from sqlalchemy import create_engine
from database import Base
from models import User, City, Order, Invoice, Conversation, Message, Wallet, Payment, Promocode, DepositRequest, CourierBalanceAddition, JWTToken
from datetime import datetime, timedelta, date
import uuid

# Test database URL - using SQLite in-memory for tests
TEST_DATABASE_URL = "sqlite:///:memory:"

# Removed event_loop fixture since we're using sync fixtures

@pytest.fixture(scope="session")
def test_engine():
    """Create test database engine."""
    # Use synchronous approach for simplicity
    from sqlalchemy import create_engine
    engine = create_engine(TEST_DATABASE_URL, echo=False)
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()

@pytest.fixture
def db_session(test_engine):
    """Create test database session."""
    from sqlalchemy.orm import sessionmaker
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()

@pytest.fixture
def test_client(test_engine):
    """Create test client for FastAPI app."""
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from sqlalchemy.orm import sessionmaker
    from unittest.mock import patch, MagicMock

    # Create a test database session factory
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    # Mock the database dependencies
    def mock_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    # Patch database functions before importing routers
    with patch('database.get_db', mock_get_db), \
         patch('database.engine', test_engine):

        # Import routers after patching
        from routers import auth, orders, cities, invoices, chat, wallets, payments, promocodes
        from database import Base

        # Create a fresh app instance for testing
        app = FastAPI()

        # Create all tables in test database
        Base.metadata.create_all(bind=test_engine)

        # Include all routers (excluding admin as requested)
        app.include_router(auth.router, prefix="/auth", tags=["auth"])
        app.include_router(orders.router, prefix="/orders", tags=["orders"])
        app.include_router(cities.router, prefix="/cities", tags=["cities"])
        app.include_router(invoices.router, prefix="/invoices", tags=["invoices"])
        app.include_router(chat.router, prefix="/chat", tags=["chat"])
        app.include_router(wallets.router, prefix="/wallets", tags=["wallets"])
        app.include_router(payments.router, prefix="/payments", tags=["payments"])
        app.include_router(promocodes.router, prefix="/promocodes", tags=["promocodes"])

        # Add root endpoint
        @app.get("/")
        def read_root():
            return {"message": "Welcome to the API"}

        client = TestClient(app)
        return client

# Mock data fixtures
@pytest.fixture
def mock_city(db_session):
    """Create a mock city."""
    city = City(name="Test City", icon="test_icon.png", active=True)
    db_session.add(city)
    db_session.commit()
    db_session.refresh(city)
    return city

# Predefined test users for consistent testing
TEST_CUSTOMER_PHONE = "+966500000001"
TEST_COURIER_PHONE = "+966500000002"

@pytest.fixture
def test_customer(db_session, mock_city):
    """Create a predefined test customer user."""
    user = User(
        phone_number=TEST_CUSTOMER_PHONE,
        email="test.customer@example.com",
        name="Test Customer",
        date_of_birth=date(1990, 1, 1),
        is_verified=True,
        role="Customer",
        city_id=mock_city.id
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture
def test_courier(db_session, mock_city):
    """Create a predefined test courier user."""
    user = User(
        phone_number=TEST_COURIER_PHONE,
        email="test.courier@example.com",
        name="Test Courier",
        date_of_birth=date(1985, 5, 15),
        national_id="1234567890",
        is_verified=True,
        role="Courier",
        city_id=mock_city.id
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture
def mock_user_customer(db_session, mock_city):
    """Create a mock customer user."""
    import random
    phone_number = f"+9665{random.randint(10000000, 99999999):08d}"
    user = User(
        phone_number=phone_number,
        email=f"customer{random.randint(1000, 9999)}@test.com",
        name="Test Customer",
        date_of_birth=date(1990, 1, 1),
        is_verified=True,
        role="Customer",
        city_id=mock_city.id
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture
def mock_user_courier(db_session, mock_city):
    """Create a mock courier user."""
    import random
    phone_number = f"+9665{random.randint(10000000, 99999999):08d}"
    user = User(
        phone_number=phone_number,
        email=f"courier{random.randint(1000, 9999)}@test.com",
        name="Test Courier",
        date_of_birth=date(1985, 5, 15),
        national_id=f"{random.randint(1000000000, 9999999999)}",
        is_verified=True,
        role="Courier",
        city_id=mock_city.id
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture
def mock_wallet_customer(db_session, mock_user_customer):
    """Create a mock wallet for customer."""
    wallet = Wallet(user_id=mock_user_customer.id, balance=10000)  # 100 SAR
    db_session.add(wallet)
    db_session.commit()
    db_session.refresh(wallet)
    return wallet

@pytest.fixture
def mock_wallet_courier(db_session, mock_user_courier):
    """Create a mock wallet for courier."""
    wallet = Wallet(user_id=mock_user_courier.id, balance=5000)  # 50 SAR
    db_session.add(wallet)
    db_session.commit()
    db_session.refresh(wallet)
    return wallet

@pytest.fixture
def mock_order(db_session, mock_user_customer, mock_user_courier, mock_city):
    """Create a mock order."""
    from models import OrderStatus
    order = Order(
        order_id=str(uuid.uuid4())[:8],
        created_by_user_id=mock_user_customer.id,
        assigned_to_user_id=mock_user_courier.id,
        description="Test order description",
        status=OrderStatus.NEW,
        city_id=mock_city.id
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    return order

@pytest.fixture
def mock_invoice(db_session, mock_order, mock_user_customer):
    """Create a mock invoice."""
    from models import InvoiceStatus
    invoice = Invoice(
        invoice_id=str(uuid.uuid4())[:8],
        order_id=mock_order.id,
        created_by_user_id=mock_user_customer.id,
        full_amount=5000,  # 50 SAR
        service_fee=500,   # 5 SAR
        order_only_price=4500,  # 45 SAR
        courier_fee=1000,  # 10 SAR
        status=InvoiceStatus.NEW,
        description="Test invoice"
    )
    db_session.add(invoice)
    db_session.commit()
    db_session.refresh(invoice)
    return invoice

@pytest.fixture
def mock_conversation(db_session, mock_user_customer, mock_user_courier, mock_order):
    """Create a mock conversation."""
    conversation = Conversation(
        customer_id=mock_user_customer.id,
        courier_id=mock_user_courier.id,
        order_id=mock_order.id,
        status="active"
    )
    db_session.add(conversation)
    db_session.commit()
    db_session.refresh(conversation)
    return conversation

@pytest.fixture
def mock_promocode(db_session):
    """Create a mock promocode."""
    promocode = Promocode(
        name="Test Promo",
        code="TEST10",
        description="10% off",
        percentage=10,
        max_value=1000,  # 10 SAR max discount
        minimum_order_value=2000,  # Min 20 SAR
        usage_limit=100,
        valid_until=datetime.utcnow() + timedelta(days=30),
        active=True,
        applicable_to="order_total"
    )
    db_session.add(promocode)
    db_session.commit()
    db_session.refresh(promocode)
    return promocode

@pytest.fixture
def mock_payment(db_session, mock_invoice, mock_user_customer):
    """Create a mock payment."""
    from models import PaymentMethod, PaymentStatus
    payment = Payment(
        invoice_id=mock_invoice.id,
        user_id=mock_user_customer.id,
        amount=5000,
        payment_method=PaymentMethod.WALLET,
        status=PaymentStatus.COMPLETED,
        wallet_balance_before=10000
    )
    db_session.add(payment)
    db_session.commit()
    db_session.refresh(payment)
    return payment
