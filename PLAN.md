# Refactoring and CI/CD Plan

## 1. Tests Folder Refactoring

### Current Structure Analysis
- Tests are currently flat in the `tests/` directory
- Each test file corresponds to a feature: auth, orders, payments, promocodes, wallets, events, couriers, security
- Common fixtures and test utilities are in `conftest.py`

### Proposed New Structure
```
tests/
├── __init__.py
├── conftest.py
├── fixtures/
│   ├── __init__.py
│   ├── auth_fixtures.py
│   ├── order_fixtures.py
│   ├── payment_fixtures.py
│   └── user_fixtures.py
├── helpers/
│   ├── __init__.py
│   ├── auth_helpers.py
│   └── db_helpers.py
├── auth/
│   ├── __init__.py
│   ├── test_send_otp.py
│   ├── test_verify_otp.py
│   ├── test_profile_completion.py
│   └── test_tokens.py
├── orders/
│   ├── __init__.py
│   ├── test_order_creation.py
│   ├── test_order_cancellation.py
│   ├── test_order_acceptance.py
│   └── test_order_completion.py
├── payments/
│   ├── __init__.py
│   ├── test_wallet_payments.py
│   ├── test_paylink_callbacks.py
│   └── test_payment_security.py
├── promocodes/
│   ├── __init__.py
│   └── test_promocodes.py
├── wallets/
│   ├── __init__.py
│   └── test_wallets.py
├── events/
│   ├── __init__.py
│   └── test_events.py
├── couriers/
│   ├── __init__.py
│   └── test_couriers.py
└── security/
    ├── __init__.py
    └── test_security.py
```

### Benefits
- Better organization and discoverability
- Easier to locate tests for specific features
- Logical grouping of related test cases
- Improved maintainability as test suite grows

## 2. GitHub Actions Workflow for Automatic Testing

### Workflow File: `.github/workflows/ci.yml`
```yaml
name: CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.9, 3.10, 3.11]
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v5
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r src/requirements.txt
        pip install pytest pytest-asyncio httpx
    
    - name: Set up test environment
      run: |
        # Create test .env file from example
        cp .env.example .env.test
        # Set test-specific environment variables
        echo "DATABASE_URL=sqlite+aiosqlite:///:memory:" >> .env.test
        echo "SECRET_KEY=test-secret-key-for-testing" >> .env.test
        echo "SMS_PROVIDER_ENABLED=false" >> .env.test
        echo "PAYLINK_TEST_MODE=true" >> .env.test
    
    - name: Run tests with coverage
      run: |
        pytest tests/ --cov=src --cov-report=xml --cov-report=term-missing
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v4
      with:
        file: ./coverage.xml
        flags: unittests
        name: codecov-umbrella
        fail_ci_if_error: false
```

### Features
- Runs on push to main/develop branches and pull requests
- Tests against multiple Python versions (3.9, 3.10, 3.11)
- Includes test coverage reporting
- Uses Codecov for coverage tracking
- Sets up proper test environment with isolated database

## 3. Patching Services in Test Cases

### Strategy
All external services in tests are already properly mocked using `unittest.mock.patch` with `AsyncMock`. Examples observed:

1. **SMS Service**: Mocked in `conftest.py` via `SMS_PROVIDER_ENABLED=false` and in tests with `@patch("utils.sms.send_sms", new_callable=AsyncMock)`
2. **Paylink Service**: Mocked in payment tests with `@patch("paylink_client.PaylinkClient.__aenter__", new_callable=AsyncMock)`
3. **WebSocket Events**: Mocked with `@patch("websocket_events.emit_*", new_callable=AsyncMock)`
4. **Email Tasks**: Mocked with `@patch("utils.background_email.send_*_background", new_callable=AsyncMock)`
5. **AWS S3**: Uses test credentials from environment variables

### No Changes Needed
The test suite already properly isolates external dependencies. All services requiring patching are already mocked appropriately in the test files.

## 4. Creating .env.example from src/.env

### Process
1. Copy content from `src/.env` to root `.env.example`
2. Replace actual values with empty placeholders or descriptive comments
3. Keep the structure and comments intact

### src/.env Content:
```
SECRET_KEY=your-secret-key-here
#DATABASE_URL=postgresql+asyncpg://giftly_admin_user:G7DmejKq7qzohYqkC66ouePtoRwLrLrj@dpg-d63r3tn5r7bs73dem4v0-a.oregon-postgres.render.com/giftly_db_z4x9
DATABASE_URL=postgresql+asyncpg://giftly_fastapi_admin:zI5K8iDDnShoeSeEAn0FfJG8vhANqMBc@giftly-fastapi-db-9rsa3r:5432/Giftly_fastapi_db
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=30
DEBUG=true

# Redis broker for TaskIQ email tasks
REDIS_URL=redis://localhost:6379

# AWS S3 Configuration
AWS_ACCESS_KEY_ID=b688412ff0d4e7f239664bdf25e9e9ea
AWS_SECRET_ACCESS_KEY=528e9224ddc1eb69861c75e7b6b8f4300230dade362ca3a51f9428bec4a9d362
AWS_S3_BUCKET_NAME=cranl-ffc1d53c-giftly-storage
STORAGE_ENDPOINT_URL=https://16e84955253346a9630f75ac258d7b72.r2.cloudflarestorage.com
```

### Resulting .env.example:
```
SECRET_KEY=your-secret-key-here
#DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST:PORT/DATABASE
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@HOST:PORT/DATABASE
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=30
DEBUG=true

# Redis broker for TaskIQ email tasks
REDIS_URL=redis://localhost:6379

# AWS S3 Configuration
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key
AWS_S3_BUCKET_NAME=your-bucket-name
STORAGE_ENDPOINT_URL=your-storage-endpoint-url
```

## Implementation Steps

### Phase 1: Test Refactoring
1. Create new directory structure under `tests/`
2. Move existing test files to appropriate feature directories
3. Update imports in test files to reflect new structure
4. Extract common fixtures to `fixtures/` directory
5. Extract helper functions to `helpers/` directory

### Phase 2: GitHub Workflow
1. Create `.github/workflows/` directory
2. Add `ci.yml` with the workflow defined above
3. Create `.env.example` in project root
4. Test workflow locally with `act` or by pushing to a test branch

### Phase 3: Verification
1. Ensure all existing tests pass after refactoring
2. Verify GitHub workflow runs successfully on test push
3. Confirm .env.example works for setting up development environment