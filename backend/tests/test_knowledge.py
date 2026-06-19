from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import uuid
import pytest
from fastapi.testclient import TestClient

from app.db.postgres import get_db
from app.main import app
from app.models.customer import Customer
from app.models.product import Product
from app.models.product_specification import ProductSpecification
from app.services.llm_service import get_llm_provider
from app.services.product_knowledge_service import ProductKnowledgeService

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
    return db_session

@pytest.fixture
def client(mock_db: MagicMock) -> TestClient:
    app.dependency_overrides[get_db] = lambda: mock_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_answer_product_question_fact(mock_db: MagicMock) -> None:
    product = Product(
        id=uuid.uuid4(),
        external_product_id="prod_123",
        name="Dynamic Widget",
        category="general",
        selling_price=100.0,
        stock_quantity=50,
        popularity_index=4.5,
        return_rate=0.02
    )
    spec = ProductSpecification(
        id=uuid.uuid4(),
        product_id=product.id,
        specification_name="Material",
        specification_value="Carbon Fiber"
    )
    
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [spec]
    mock_db.execute.return_value = mock_result
    
    mock_llm = MagicMock()
    service = ProductKnowledgeService(llm=mock_llm)
    
    ans = await service.answer_product_question(product, "What material is this made of?", mock_db)
    assert "[Catalog-Backed Fact]" in ans
    assert "Material" in ans
    assert "Carbon Fiber" in ans

@pytest.mark.asyncio
async def test_compare_products(mock_db: MagicMock) -> None:
    p1 = Product(id=uuid.uuid4(), external_product_id="p1", name="Product One", selling_price=100.0, stock_quantity=10, return_rate=0.01, category="test")
    p2 = Product(id=uuid.uuid4(), external_product_id="p2", name="Product Two", selling_price=120.0, stock_quantity=20, return_rate=0.02, category="test")
    
    spec = ProductSpecification(id=uuid.uuid4(), product_id=p1.id, specification_name="Warranty", specification_value="2 years")
    
    resolver_mock = MagicMock()
    resolver_mock.resolve_products = AsyncMock(return_value=[p1, p2])
    
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.side_effect = [[spec], []]
    mock_db.execute.return_value = mock_result
    
    mock_llm = MagicMock()
    service = ProductKnowledgeService(llm=mock_llm)
    
    with patch("app.services.product_knowledge_service.ProductResolver", return_value=resolver_mock):
        comparison = await service.compare_products("Compare p1 and p2", p1, mock_db)
        assert comparison["resolved_count"] == 2
        assert "Warranty" in comparison["spec_names"]
        assert len(comparison["products"]) == 2
        assert comparison["products"][0]["name"] == "Product One"
        assert comparison["products"][0]["specifications"]["Warranty"] == "2 years"
