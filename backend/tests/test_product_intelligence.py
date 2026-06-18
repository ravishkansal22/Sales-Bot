"""Unit and integration tests for product and customer intelligence services and API.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.db.postgres import get_db
from app.main import app
from app.models.customer import Customer
from app.models.order import Order
from app.models.product import Product
from app.services.customer_profile_builder import CustomerProfileBuilder
from app.services.llm.base import LLMProvider
from app.services.product_resolver import ProductResolver
from app.services.product_service import ProductService


# ---------------------------------------------------------------------------
# Mock LLM Provider for Resolver Fallback
# ---------------------------------------------------------------------------

class MockResolverLLMProvider(LLMProvider):
    """Mock LLM Provider returning query extraction structured response."""

    async def generate(self, prompt: str, system_prompt: str, response_model: type[BaseModel]) -> BaseModel:
        if response_model.__name__ == "SearchExtraction":
            return response_model(
                query="cricket bat",
                is_product_related=True,
            )
        raise ValueError(f"Unknown response model: {response_model}")


# ---------------------------------------------------------------------------
# Pytest Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_app_lifespan() -> None:
    """Mock database and Redis initialization in FastAPI lifespan context."""
    with patch("app.main.init_db", new_callable=AsyncMock) as _, \
         patch("app.main.close_db", new_callable=AsyncMock) as _, \
         patch("app.main.init_redis", new_callable=AsyncMock) as _, \
         patch("app.main.close_redis", new_callable=AsyncMock) as _:
        yield


@pytest.fixture
def mock_db() -> MagicMock:
    """Fixture for a mocked async SQLAlchemy Session."""
    db_session = MagicMock()
    db_session.execute = AsyncMock()
    db_session.get = AsyncMock()
    db_session.flush = AsyncMock()
    db_session.commit = AsyncMock()
    db_session.rollback = AsyncMock()
    return db_session


@pytest.fixture
def client(mock_db: MagicMock) -> TestClient:
    """Fixture for FastAPI TestClient with overridden db dependency."""
    app.dependency_overrides[get_db] = lambda: mock_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# ProductService Tests
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_product_service_get_by_id(mock_db: MagicMock) -> None:
    product_uuid = uuid.uuid4()
    mock_product = Product(
        id=product_uuid,
        external_product_id="P100",
        name="Test Cricket Bat",
        category="Sports",
        selling_price=150.0,
        cost_price=90.0,
        minimum_price=110.0,
        target_margin=0.4,
        stock_quantity=10,
        popularity_index=4.5,
        return_rate=0.05,
    )
    
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = mock_product
    mock_db.execute.return_value = mock_result
    
    prod = await ProductService.get_product_by_id(mock_db, product_uuid)
    assert prod is not None
    assert prod.id == product_uuid
    assert prod.name == "Test Cricket Bat"


@pytest.mark.anyio
async def test_product_service_get_by_external_id(mock_db: MagicMock) -> None:
    product_uuid = uuid.uuid4()
    mock_product = Product(
        id=product_uuid,
        external_product_id="P100",
        name="Test Cricket Bat",
        category="Sports",
        selling_price=150.0,
        cost_price=90.0,
        minimum_price=110.0,
        target_margin=0.4,
        stock_quantity=10,
        popularity_index=4.5,
        return_rate=0.05,
    )
    
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = mock_product
    mock_db.execute.return_value = mock_result
    
    prod = await ProductService.get_product_by_external_id(mock_db, "P100")
    assert prod is not None
    assert prod.external_product_id == "P100"
    assert prod.name == "Test Cricket Bat"


@pytest.mark.anyio
async def test_product_service_search_products(mock_db: MagicMock) -> None:
    mock_products = [
        Product(
            id=uuid.uuid4(),
            external_product_id="P100",
            name="Super Cricket Bat",
            category="Sports",
            selling_price=150.0,
            cost_price=90.0,
            minimum_price=110.0,
            target_margin=0.4,
            stock_quantity=10,
            popularity_index=4.5,
            return_rate=0.05,
        )
    ]
    
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = mock_products
    mock_db.execute.return_value = mock_result
    
    # Test text query
    results = await ProductService.search_products(mock_db, "cricket")
    assert len(results) == 1
    assert results[0].name == "Super Cricket Bat"

    # Test empty query (should return popular products)
    results_empty = await ProductService.search_products(mock_db, "")
    assert len(results_empty) == 1


# ---------------------------------------------------------------------------
# ProductResolver Tests
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_product_resolver_direct_match(mock_db: MagicMock) -> None:
    mock_products = [
        Product(
            id=uuid.uuid4(),
            external_product_id="P100",
            name="Kookaburra Cricket Bat",
            category="Sports Equipment",
            selling_price=200.0,
            cost_price=120.0,
            minimum_price=150.0,
            target_margin=0.4,
            stock_quantity=5,
            popularity_index=4.8,
            return_rate=0.02,
        )
    ]
    
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = mock_products
    mock_db.execute.return_value = mock_result
    
    resolver = ProductResolver()
    # "I want to buy a cricket bat please" -> stop words removed -> query is "cricket bat"
    resolved = await resolver.resolve_products("I want to buy a cricket bat please", mock_db)
    assert len(resolved) == 1
    assert resolved[0].name == "Kookaburra Cricket Bat"


@pytest.mark.anyio
async def test_product_resolver_llm_fallback(mock_db: MagicMock) -> None:
    # First query returns empty (no direct match)
    mock_result_empty = MagicMock()
    mock_result_empty.scalars.return_value.all.return_value = []
    
    # Second query (triggered after LLM extracts "cricket bat") returns the product
    mock_product = Product(
        id=uuid.uuid4(),
        external_product_id="P100",
        name="Kookaburra Cricket Bat",
        category="Sports Equipment",
        selling_price=200.0,
        cost_price=120.0,
        minimum_price=150.0,
        target_margin=0.4,
        stock_quantity=5,
        popularity_index=4.8,
        return_rate=0.02,
    )
    mock_result_found = MagicMock()
    mock_result_found.scalars.return_value.all.return_value = [mock_product]
    
    mock_db.execute.side_effect = [mock_result_empty, mock_result_found]
    
    mock_llm = MockResolverLLMProvider()
    resolver = ProductResolver(llm=mock_llm)
    
    # The message is hard to parse directly, triggering fallback
    resolved = await resolver.resolve_products("give me that thing for hitting wickets", mock_db)
    assert len(resolved) == 1
    assert resolved[0].name == "Kookaburra Cricket Bat"


# ---------------------------------------------------------------------------
# CustomerProfileBuilder Tests
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_customer_profile_builder(mock_db: MagicMock) -> None:
    cust_uuid = uuid.uuid4()
    mock_customer = Customer(
        id=cust_uuid,
        external_customer_id="C500",
        name="Jane Doe",
        email="jane@example.com",
        customer_segment="High-Value",
        total_spend=1200.0,
        average_order_value=300.0,
        total_orders=4,
    )
    
    prod_uuid = uuid.uuid4()
    mock_product = Product(
        id=prod_uuid,
        external_product_id="P100",
        name="Cricket Bat",
        category="Sports",
        selling_price=200.0,
        cost_price=100.0,
        minimum_price=130.0,
        target_margin=0.5,
        stock_quantity=10,
        popularity_index=4.0,
        return_rate=0.01,
    )
    
    # Setup mock orders
    order1 = Order(
        id=uuid.uuid4(),
        customer_id=cust_uuid,
        product_id=prod_uuid,
        purchase_price=180.0,  # Below selling price (200.0) -> counts as discount
        purchase_date=datetime.now(timezone.utc),
        payment_method="Credit Card",
        delivery_status="Delivered",
        product=mock_product,
    )
    order2 = Order(
        id=uuid.uuid4(),
        customer_id=cust_uuid,
        product_id=prod_uuid,
        purchase_price=200.0,  # Matches list price
        purchase_date=datetime.now(timezone.utc),
        payment_method="Credit Card",
        delivery_status="Returned",  # Counts as returned
        product=mock_product,
    )
    
    mock_result_customer = MagicMock()
    mock_result_customer.scalars.return_value.first.return_value = mock_customer
    
    mock_result_orders = MagicMock()
    mock_result_orders.scalars.return_value.all.return_value = [order1, order2]
    
    mock_db.execute.side_effect = [mock_result_customer, mock_result_orders]
    
    summary = await CustomerProfileBuilder.build_summary(mock_db, str(cust_uuid))
    
    assert summary.customer_id == str(cust_uuid)
    assert summary.total_orders == 4
    assert summary.total_spend == 1200.0
    assert summary.average_spend == 300.0
    assert summary.segment == "High-Value"
    assert summary.return_rate == 0.25  # 1 returned / 4 total orders
    assert summary.repeated_discount_purchases_count == 1  # order1 paid 180 < 200
    assert "Sports" in summary.frequent_categories


# ---------------------------------------------------------------------------
# API Catalog Endpoints Tests
# ---------------------------------------------------------------------------

def test_list_products_endpoint(client: TestClient, mock_db: MagicMock) -> None:
    mock_product = Product(
        id=uuid.uuid4(),
        external_product_id="P100",
        name="Cricket Bat",
        category="Sports",
        selling_price=100.0,
        cost_price=60.0,
        minimum_price=80.0,
        target_margin=0.4,
        stock_quantity=10,
        popularity_index=4.0,
        return_rate=0.01,
    )
    
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_product]
    mock_db.execute.return_value = mock_result
    
    response = client.get("/api/v1/products?page=1&limit=5")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["external_product_id"] == "P100"
    assert data[0]["name"] == "Cricket Bat"


def test_search_products_endpoint(client: TestClient, mock_db: MagicMock) -> None:
    mock_product = Product(
        id=uuid.uuid4(),
        external_product_id="P100",
        name="Cricket Bat",
        category="Sports",
        selling_price=100.0,
        cost_price=60.0,
        minimum_price=80.0,
        target_margin=0.4,
        stock_quantity=10,
        popularity_index=4.0,
        return_rate=0.01,
    )
    
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_product]
    mock_db.execute.return_value = mock_result
    
    response = client.get("/api/v1/products/search?q=cricket")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Cricket Bat"


@patch("app.api.catalog.get_llm_provider")
def test_recommend_products_endpoint(mock_get_llm: MagicMock, client: TestClient, mock_db: MagicMock) -> None:
    mock_get_llm.return_value = MockResolverLLMProvider()
    
    mock_product = Product(
        id=uuid.uuid4(),
        external_product_id="P100",
        name="Kookaburra Cricket Bat",
        category="Sports Equipment",
        selling_price=200.0,
        cost_price=120.0,
        minimum_price=150.0,
        target_margin=0.4,
        stock_quantity=5,
        popularity_index=4.8,
        return_rate=0.02,
    )
    
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_product]
    mock_db.execute.return_value = mock_result
    
    response = client.get("/api/v1/products/recommendations?q=cricket")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Kookaburra Cricket Bat"


def test_get_product_endpoint_by_id(client: TestClient, mock_db: MagicMock) -> None:
    prod_uuid = uuid.uuid4()
    mock_product = Product(
        id=prod_uuid,
        external_product_id="P100",
        name="Cricket Bat",
        category="Sports",
        selling_price=100.0,
        cost_price=60.0,
        minimum_price=80.0,
        target_margin=0.4,
        stock_quantity=10,
        popularity_index=4.0,
        return_rate=0.01,
    )
    
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = mock_product
    mock_db.execute.return_value = mock_result
    
    # By UUID
    response = client.get(f"/api/v1/products/{prod_uuid}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Cricket Bat"
    assert data["external_product_id"] == "P100"


def test_get_product_endpoint_by_external_id(client: TestClient, mock_db: MagicMock) -> None:
    prod_uuid = uuid.uuid4()
    mock_product = Product(
        id=prod_uuid,
        external_product_id="P100",
        name="Cricket Bat",
        category="Sports",
        selling_price=100.0,
        cost_price=60.0,
        minimum_price=80.0,
        target_margin=0.4,
        stock_quantity=10,
        popularity_index=4.0,
        return_rate=0.01,
    )
    
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = mock_product
    mock_db.execute.return_value = mock_result
    
    # By external ID
    response = client.get("/api/v1/products/P100")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Cricket Bat"


def test_get_product_endpoint_not_found(client: TestClient, mock_db: MagicMock) -> None:
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = None
    mock_db.execute.return_value = mock_result
    
    response = client.get("/api/v1/products/P99999")
    assert response.status_code == 404


def test_get_customer_endpoint(client: TestClient, mock_db: MagicMock) -> None:
    cust_uuid = uuid.uuid4()
    mock_customer = Customer(
        id=cust_uuid,
        external_customer_id="C500",
        name="Jane Doe",
        email="jane@example.com",
        customer_segment="High-Value",
        total_spend=1200.0,
        average_order_value=300.0,
        total_orders=4,
    )
    
    # We patch customer database get
    mock_db.get.return_value = mock_customer
    
    # We patch profile builder build_summary
    mock_summary = CustomerProfileBuilder.build_summary
    
    mock_result_orders = MagicMock()
    mock_result_orders.scalars.return_value.all.return_value = []
    
    mock_result_customer = MagicMock()
    mock_result_customer.scalars.return_value.first.return_value = mock_customer
    mock_db.execute.side_effect = [mock_result_customer, mock_result_orders]
    
    response = client.get(f"/api/v1/customers/{cust_uuid}")
    assert response.status_code == 200
    data = response.json()
    assert data["customer"]["name"] == "Jane Doe"
    assert data["customer"]["customer_segment"] == "High-Value"
    assert "history_summary" in data
