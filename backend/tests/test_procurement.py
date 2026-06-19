from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import pytest
from fastapi.testclient import TestClient

from app.db.postgres import get_db
from app.main import app
from app.models.customer import Customer
from app.models.product import Product
from app.models.locked_deal import LockedDeal

@pytest.fixture(autouse=True)
def mock_app_lifespan() -> None:
    with patch("app.main.init_db", new_callable=AsyncMock) as _, \
         patch("app.main.close_db", new_callable=AsyncMock) as _, \
         patch("app.main.init_redis", new_callable=AsyncMock) as _, \
         patch("app.main.close_redis", new_callable=AsyncMock) as _:
        yield

@pytest.fixture
def mock_db() -> MagicMock:
    db_session = MagicMock()
    db_session.execute = AsyncMock()
    db_session.flush = AsyncMock()
    db_session.commit = AsyncMock()
    db_session.rollback = AsyncMock()
    db_session.delete = AsyncMock()
    return db_session

@pytest.fixture
def client(mock_db: MagicMock) -> TestClient:
    app.dependency_overrides[get_db] = lambda: mock_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

def test_lock_deal_endpoint(client: TestClient, mock_db: MagicMock) -> None:
    mock_cust = Customer(id=uuid.uuid4(), external_customer_id="cust_123", name="Test Customer")
    mock_prod = Product(id=uuid.uuid4(), external_product_id="prod_123", name="Test Product", selling_price=100.0, cost_price=60.0)
    
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.side_effect = [mock_cust, mock_prod, None]
    mock_db.execute.return_value = mock_result
    
    payload = {
        "customer_id": "cust_123",
        "product_id": "prod_123",
        "quantity": 5,
        "negotiated_price": 90.0,
        "concessions": ["Free SLA Upgrade"],
        "strategy": "balanced",
        "confidence_score": 0.95
    }
    
    response = client.post("/api/v1/procurement/lock", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "success"

def test_get_cart_endpoint(client: TestClient, mock_db: MagicMock) -> None:
    mock_cust = Customer(id=uuid.uuid4(), external_customer_id="cust_123")
    mock_prod = Product(id=uuid.uuid4(), external_product_id="prod_123", name="Test Product", selling_price=100.0, stock_quantity=10, return_rate=0.0)
    
    mock_deal = LockedDeal(
        id=uuid.uuid4(),
        customer_id=mock_cust.id,
        product_id=mock_prod.id,
        quantity=5,
        negotiated_price=90.0,
        concessions=["Free SLA Upgrade"],
        strategy="balanced",
        confidence_score=0.95,
        product=mock_prod
    )
    
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = mock_cust
    mock_result.scalars.return_value.all.return_value = [mock_deal]
    mock_db.execute.return_value = mock_result
    
    response = client.get("/api/v1/procurement/cart?customer_id=cust_123")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert len(data["items"]) == 1
    assert data["summary"]["total_items"] == 5
    assert data["summary"]["total_savings"] == 50.0

def test_update_quantity_endpoint(client: TestClient, mock_db: MagicMock) -> None:
    deal_id = str(uuid.uuid4())
    response = client.put(f"/api/v1/procurement/cart/{deal_id}/quantity", json={"quantity": 10})
    assert response.status_code == 200
    assert response.json()["status"] == "success"

def test_delete_cart_item(client: TestClient, mock_db: MagicMock) -> None:
    deal_id = str(uuid.uuid4())
    response = client.delete(f"/api/v1/procurement/cart/{deal_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
