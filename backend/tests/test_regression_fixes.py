from __future__ import annotations

import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.db.postgres import get_db
from app.main import app
from app.models.customer import Customer
from app.models.product import Product
from app.models.product_specification import ProductSpecification
from app.models.locked_deal import LockedDeal
from app.services.product_knowledge_service import ProductKnowledgeService
from app.core.strategy_optimizer import StrategyOptimizer
from app.schemas.simulation import SimulationOutput, SimulationRollout, OptimizationMode

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

# ===========================================================================
# 1. Procurement Validation Endpoint Tests
# ===========================================================================

def test_procurement_validation_lock_rejections(client: TestClient, mock_db: MagicMock) -> None:
    mock_cust = Customer(id=uuid.uuid4(), external_customer_id="cust_123", name="Test Customer")
    mock_prod = Product(
        id=uuid.uuid4(),
        external_product_id="prod_123",
        name="Test Product",
        selling_price=100.0,
        cost_price=60.0,
        minimum_price=70.0
    )
    
    # 1. Reject price <= 0
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.side_effect = [mock_cust, mock_prod, None]
    mock_db.execute.return_value = mock_result
    
    payload = {
        "customer_id": "cust_123",
        "product_id": "prod_123",
        "quantity": 5,
        "negotiated_price": 0.0,
        "concessions": [],
        "strategy": "balanced",
        "confidence_score": 0.95
    }
    
    response = client.post("/api/v1/procurement/lock", json=payload)
    assert response.status_code == 400
    assert "must be greater than zero" in response.json()["detail"]

    # 2. Reject price < minimum_price (70.0) under default strict rules
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.side_effect = [mock_cust, mock_prod, None]
    mock_db.execute.return_value = mock_result
    payload["negotiated_price"] = 65.0
    
    response = client.post("/api/v1/procurement/lock", json=payload)
    assert response.status_code == 400
    assert "below the minimum allowed floor price" in response.json()["detail"]

    # 3. Reject price < cost_price (60.0) under default strict rules
    # We patch ALLOW_BELOW_MINIMUM to True so minimum_price check is bypassed, triggering cost_price check
    with patch("app.core.config_layer.settings.ALLOW_BELOW_MINIMUM", True):
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.side_effect = [mock_cust, mock_prod, None]
        mock_db.execute.return_value = mock_result
        payload["negotiated_price"] = 55.0
        
        response = client.post("/api/v1/procurement/lock", json=payload)
        assert response.status_code == 400
        assert "below the product cost price" in response.json()["detail"]

def test_procurement_validation_override_configs(client: TestClient, mock_db: MagicMock) -> None:
    mock_cust = Customer(id=uuid.uuid4(), external_customer_id="cust_123", name="Test Customer")
    mock_prod = Product(
        id=uuid.uuid4(),
        external_product_id="prod_123",
        name="Test Product",
        selling_price=100.0,
        cost_price=60.0,
        minimum_price=70.0
    )

    payload = {
        "customer_id": "cust_123",
        "product_id": "prod_123",
        "quantity": 5,
        "negotiated_price": 55.0,
        "concessions": [],
        "strategy": "balanced",
        "confidence_score": 0.95
    }

    # Patch ALLOW_BELOW_MINIMUM and ALLOW_BELOW_COST to True
    with patch("app.core.config_layer.settings.ALLOW_BELOW_MINIMUM", True), \
         patch("app.core.config_layer.settings.ALLOW_BELOW_COST", True):
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.side_effect = [mock_cust, mock_prod, None]
        mock_db.execute.return_value = mock_result

        response = client.post("/api/v1/procurement/lock", json=payload)
        assert response.status_code == 200
        assert response.json()["status"] == "success"

# ===========================================================================
# 2. Product Specification Semantic Synonym Matching
# ===========================================================================

@pytest.mark.anyio
async def test_product_spec_semantic_synonyms(mock_db: MagicMock) -> None:
    mock_prod = Product(
        id=uuid.uuid4(),
        external_product_id="prod_123",
        name="Tech Gadget",
        category="Electronics",
        selling_price=500.0,
        stock_quantity=10,
        popularity_index=4.5,
        return_rate=1.2
    )

    mock_spec = ProductSpecification(
        id=uuid.uuid4(),
        product_id=mock_prod.id,
        specification_name="CPU",
        specification_value="Hexa-core Snapdragon"
    )

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_spec]
    mock_db.execute.return_value = mock_result

    llm = MagicMock()
    service = ProductKnowledgeService(llm=llm)

    # Query with processor synonym "processor" should match "CPU" specification name semantically
    ans = await service.answer_product_question(mock_prod, "What processor is in it?", mock_db)
    assert ans.source == "catalog"
    assert "Snapdragon" in ans.customer_response
    assert ans.resolved_attribute == "processor"

    # Query with SoC synonym should also match
    ans = await service.answer_product_question(mock_prod, "what SoC does it run?", mock_db)
    assert ans.source == "catalog"
    assert "Snapdragon" in ans.customer_response

# ===========================================================================
# 3. LLM Fallback Gating & Gated Confidence Estimation
# ===========================================================================

@pytest.mark.anyio
async def test_llm_fallback_estimation_gated(mock_db: MagicMock) -> None:
    mock_prod = Product(
        id=uuid.uuid4(),
        name="Classic Novel",
        category="Books",
        selling_price=15.0,
        stock_quantity=100,
        popularity_index=3.0,
        return_rate=0.0
    )

    # Mock database to return empty list for specifications
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    llm = AsyncMock()
    # Mock LLM estimate response
    mock_estimate = MagicMock()
    mock_estimate.answer = "Paperback"
    mock_estimate.confidence = 0.90
    mock_estimate.reasoning = "Category standards"
    llm.generate.return_value = mock_estimate

    service = ProductKnowledgeService(llm=llm)

    # 1. By default, ENABLE_SPEC_ESTIMATION is False, so it should return unavailable
    with patch("app.core.config_layer.settings.ENABLE_SPEC_ESTIMATION", False):
        ans = await service.answer_product_question(mock_prod, "what color is the cover?", mock_db)
        assert ans.source == "none"
        assert "unavailable" in ans.customer_response.lower()

    # 2. When ENABLE_SPEC_ESTIMATION is True and confidence (0.90) is >= threshold (0.85), it returns estimate
    if hasattr(ProductKnowledgeService, "_in_memory_cache"):
        ProductKnowledgeService._in_memory_cache.clear()
        
    with patch("app.core.config_layer.settings.ENABLE_SPEC_ESTIMATION", True), \
         patch("app.core.config_layer.settings.SPEC_ESTIMATION_CONFIDENCE_THRESHOLD", 0.85):
        ans = await service.answer_product_question(mock_prod, "what color is the cover?", mock_db)
        assert ans.source == "general_knowledge"
        assert "estimated to be" in ans.customer_response
        assert "Paperback" in ans.customer_response

    # 3. When confidence (0.90) is < threshold (0.95), it gates it and returns unavailable
    if hasattr(ProductKnowledgeService, "_in_memory_cache"):
        ProductKnowledgeService._in_memory_cache.clear()
        
    with patch("app.core.config_layer.settings.ENABLE_SPEC_ESTIMATION", True), \
         patch("app.core.config_layer.settings.SPEC_ESTIMATION_CONFIDENCE_THRESHOLD", 0.95):
        ans = await service.answer_product_question(mock_prod, "what color is the cover?", mock_db)
        assert ans.source == "none"

# ===========================================================================
# 4. Strategy Optimizer Safety Guard Bounds
# ===========================================================================

def test_strategy_optimizer_clamping_and_validation() -> None:
    # Set up simple mock simulation
    sim = SimulationOutput(
        strategy_name="discount",
        offer_type="discount",
        discount_percent=10.0,
        bundle_value=0.0,
        reasoning="Offer discount.",
        rollouts=[
            SimulationRollout(
                rollout_id="r1",
                reasoning="Standard reaction",
                strategy_fit=0.8,
                risk_score=0.2,
                customer_reaction=None,
                timeline_events=[]
            )
        ],
        average_close_probability=0.8,
        average_risk_score=0.1,
        average_expected_profit=100.0,
        average_expected_value=80.0,
        average_gross_margin_retention=0.6,
        concessions=[]
    )

    # 1. Zero discount should map exactly to list price
    winner = StrategyOptimizer.optimize(
        simulations=[sim],
        mode=OptimizationMode.BALANCED,
        stock_quantity=50,
        has_pricing_request=True,
        dynamic_ceiling=0.0,  # Forces discount to 0%
        list_price=100.0,
        requested_discount_percent=0.0
    )
    assert winner.actual_offer_discount == 0.0
    assert winner.actual_offer_price == 100.0

    # 2. Strict validation raises ValueError on <= 0 calculated price
    with patch("app.core.config_layer.settings.STRICT_NEGOTIATION_VALIDATION", True):
        # We simulate a situation where raw calculations result in <= 0 price
        # (e.g. discount is extremely high or negative pricing occurs)
        # To simulate this without fully reproducing simulation score loops, we optimize
        # where list_price is positive but actual_offer_price calculation collapses.
        # Let's verify ValueError is raised if validation fails.
        with pytest.raises(ValueError):
            # If dynamic ceiling allows very high discount, say 150% (leading to negative price)
            sim_high = SimulationOutput(
                strategy_name="discount",
                offer_type="discount",
                discount_percent=150.0,
                bundle_value=0.0,
                reasoning="Offer discount.",
                rollouts=[
                    SimulationRollout(
                        rollout_id="r1",
                        reasoning="Standard reaction",
                        strategy_fit=0.8,
                        risk_score=0.2,
                        customer_reaction=None,
                        timeline_events=[]
                    )
                ],
                average_close_probability=0.8,
                average_risk_score=0.1,
                average_expected_profit=100.0,
                average_expected_value=80.0,
                average_gross_margin_retention=0.6,
                concessions=[]
            )
            StrategyOptimizer.optimize(
                simulations=[sim_high],
                mode=OptimizationMode.BALANCED,
                stock_quantity=50,
                has_pricing_request=True,
                dynamic_ceiling=150.0,
                list_price=100.0,
                requested_discount_percent=150.0
            )
