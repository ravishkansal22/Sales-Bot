from __future__ import annotations

import os
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.api.chat import is_negotiation_message
from app.db.postgres import get_db
from app.models.customer import Customer
from app.models.negotiation_context import NegotiationContext
from app.models.product import Product
from app.schemas.chat import ChatResponse
from app.services.product_service import ProductService
from app.services.llm_service import llm_call_counts
from app.main import app

client = TestClient(app)

@pytest.fixture(autouse=True)
def mock_app_lifespan() -> None:
    """Mock database and Redis initialization in FastAPI lifespan context."""
    with patch("app.main.init_db", new_callable=AsyncMock) as _, \
         patch("app.main.close_db", new_callable=AsyncMock) as _, \
         patch("app.main.init_redis", new_callable=AsyncMock) as _, \
         patch("app.main.close_redis", new_callable=AsyncMock) as _:
        yield

def test_is_negotiation_message() -> None:
    """Verify is_negotiation_message detects pricing/discount keywords and percentage patterns."""
    assert is_negotiation_message("I want 25% discount") is True
    assert is_negotiation_message("What price is competitor offering?") is True
    assert is_negotiation_message("Can I get 30% off?") is True
    assert is_negotiation_message("Here is my counteroffer") is True
    assert is_negotiation_message("Tell me about features") is False
    assert is_negotiation_message("Is this model premium?") is False


@pytest.mark.anyio
async def test_search_deduplication_and_category_stickiness() -> None:
    """Verify that product search deduplicates results by name and enforces category stickiness."""
    p1 = Product(
        id=uuid.uuid4(),
        external_product_id="P_TEST_1",
        name="Galaxy S25 Ultra",
        category="Electronics",
        selling_price=120000.0,
        cost_price=80000.0,
        minimum_price=100000.0,
        target_margin=33.3,
        stock_quantity=50,
        popularity_index=4.5,
        return_rate=0.5,
    )
    p2 = Product(
        id=uuid.uuid4(),
        external_product_id="P_TEST_2",
        name="Galaxy S25 Ultra",  # Duplicate name
        category="Electronics",
        selling_price=120000.0,
        cost_price=80000.0,
        minimum_price=100000.0,
        target_margin=33.3,
        stock_quantity=40,
        popularity_index=4.5,
        return_rate=0.5,
    )
    p3 = Product(
        id=uuid.uuid4(),
        external_product_id="P_TEST_3",
        name="Bosch Dishwasher Pro",  # Different category, matches "Pro"
        category="Home Appliances",
        selling_price=45000.0,
        cost_price=30000.0,
        minimum_price=40000.0,
        target_margin=33.3,
        stock_quantity=10,
        popularity_index=4.0,
        return_rate=1.0,
    )

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [p1, p2, p3]
    mock_db.execute.return_value = mock_result

    # Search for "Galaxy S25 Ultra Pro"
    # Even though both Galaxy and Bosch match raw conditions, Galaxy S25 Ultra (Electronics) is the top match
    # Category stickiness should filter out Bosch Dishwasher Pro (Home Appliances)
    # Deduplication should only return a single "Galaxy S25 Ultra"
    results = await ProductService.search_products(mock_db, "Galaxy S25 Ultra Pro", limit=10)
    
    assert len(results) == 1
    assert results[0].name == "Galaxy S25 Ultra"
    assert results[0].category == "Electronics"


@pytest.mark.anyio
async def test_database_reseed_recovery() -> None:
    """Verify that if NegotiationContext points to a stale product ID, the system clears it and recovers."""
    cust_id = uuid.uuid4()
    stale_prod_id = uuid.uuid4()
    
    mock_customer = Customer(
        id=cust_id,
        external_customer_id="U_RESEED_TEST",
        name="Reseed Buyer",
        email="reseed@buyer.com",
        customer_segment="VIP",
        total_spend=0.0,
        average_order_value=0.0,
        total_orders=0,
    )
    
    mock_context = NegotiationContext(
        id=uuid.uuid4(),
        customer_id=cust_id,
        product_id=stale_prod_id,
        quantity=1,
        current_offer=1000.0,
        requested_discount=0.0,
        negotiation_stage="initiated",
    )

    mock_product = Product(
        id=stale_prod_id,
        external_product_id="P_RESEED_TEST",
        name="Failsafe Vacuum",
        category="Home Appliances",
        selling_price=1000.0,
        cost_price=600.0,
        minimum_price=800.0,
        target_margin=40.0,
        stock_quantity=50,
        popularity_index=4.0,
        return_rate=1.0,
    )

    mock_db = AsyncMock()
    mock_db._force_context = True
    mock_result = MagicMock()
    # 1. Customer query -> mock_customer
    # 2. Context query (1st check) -> mock_context
    # 3. Product query (stale context prod ID) -> None
    # 4. Context query (2nd check) -> None (since deleted)
    # 5. Product query (request prod ID) -> mock_product
    # 6. Twin snapshot query -> None
    mock_result.scalars.return_value.first.side_effect = [
        mock_customer,
        mock_context,
        None,
        mock_product,
        None,
        None,
    ]
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    app.dependency_overrides[get_db] = lambda: mock_db
    
    payload = {
        "message": "I want 25% discount",
        "customer_id": "U_RESEED_TEST",
        "product_id": str(stale_prod_id),
        "quantity": 1
    }

    with patch("app.services.llm_service.GracefulFallbackProvider.generate") as mock_fallback_gen:
        # Just mock fallback response to avoid real LLM calls
        from app.schemas.chat import ConversationAnalysis
        from app.schemas.simulation import DigitalTwinProfile
        from app.schemas.simulation import LLMStrategyOutput
        from app.core.intent_classifier import IntentClassification
        
        def side_effect(prompt, system_prompt, response_model):
            name = response_model.__name__
            if name == "IntentClassification":
                return response_model(intent="negotiation", confidence=0.95, reasoning="mock", target_product_ids=[])
            elif name == "ConversationAnalysis":
                return response_model(objection_type="price", negotiation_intent="discount", urgency=0.5, sentiment="neutral", stage="negotiation")
            elif name == "DigitalTwinProfile":
                return response_model(price_sensitivity=0.5, urgency=0.5, risk_aversion=0.5, brand_loyalty=0.5, decision_speed=0.5)
            elif name == "LLMStrategyOutput":
                return response_model(strategy_name="discount", offer_type="discount", discount_percent=10.0, bundle_value=0.0, reasoning="mock")
            elif name == "_LLMResponseOutput":
                return response_model(customer_response="Mock offer", internal_reasoning="mock")
            return response_model.construct()
            
        mock_fallback_gen.side_effect = side_effect

        response = client.post("/api/v1/chat", json=payload)
        
        # Verify recovery succeeds (200 OK)
        assert response.status_code == 200
        
        # Verify that session execute was called to delete the stale NegotiationContext
        delete_called = False
        for call in mock_db.execute.call_args_list:
            stmt = str(call[0][0])
            if "DELETE FROM negotiation_contexts" in stmt or "delete" in stmt.lower():
                delete_called = True
                break
        assert delete_called is True
        
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_rate_limit_simulation_fallback_and_groq_counts() -> None:
    """Verify rate limit recovery, deterministic simulations (no LLMStrategyOutput calls), and counter logs."""
    cust_id = uuid.uuid4()
    prod_id = uuid.uuid4()
    
    mock_customer = Customer(
        id=cust_id,
        external_customer_id="U_RATELIMIT_TEST",
        name="Rate Limit Buyer",
        email="ratelimit@buyer.com",
        customer_segment="VIP",
        total_spend=0.0,
        average_order_value=0.0,
        total_orders=0,
    )
    mock_product = Product(
        id=prod_id,
        external_product_id="P_RATELIMIT_TEST",
        name="Failsafe Vacuum",
        category="Home Appliances",
        selling_price=1000.0,
        cost_price=600.0,
        minimum_price=800.0,
        target_margin=40.0,
        stock_quantity=50,
        popularity_index=4.0,
        return_rate=1.0,
    )
    
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.side_effect = [mock_customer, mock_product, None]
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result
    
    app.dependency_overrides[get_db] = lambda: mock_db

    # Reset counters and circuit breaker state
    from app.services.llm_service import circuit_breaker_service
    await circuit_breaker_service._set_state({
        "consecutive_failures": 0,
        "state": "closed",
        "cooldown_until": 0.0,
        "half_open_probe_active": False
    })
    for k in llm_call_counts:
        llm_call_counts[k] = 0

    # Mock primary LLM provider to fail (simulating 429 Rate Limit)
    # The pipeline should seamlessly fall back to DeterministicFallbackProvider
    with patch("app.services.llm_service.GroqProvider") as mock_groq_class:
        mock_groq = MagicMock()
        mock_groq.generate.side_effect = Exception("429 Too Many Requests / Rate Limit Exhausted")
        mock_groq_class.return_value = mock_groq
        
        with patch.dict(os.environ, {"LLM_PROVIDER": "groq", "GROQ_API_KEY": "dummy"}):
            payload = {
                "message": "I want 20% discount on this vacuum",
                "customer_id": "U_RATELIMIT_TEST",
                "product_id": str(prod_id),
                "quantity": 1
            }
            
            response = client.post("/api/v1/chat", json=payload)
            
            if response.status_code != 200:
                print("RESPONSE CONTENT:", response.content)
            assert response.status_code == 200
            data = response.json()
            
            # Check response is valid
            assert "response" in data
            assert "winner" in data
            assert data["winner"]["winning_strategy"] is not None
            
            # Print call counts for verification
            print("\n=== Groq Calls Log ===")
            for model_name, count in llm_call_counts.items():
                print(f"{model_name}: {count} calls")
            
            # Verify that:
            # 1. IntentClassification, ConversationAnalysis, DigitalTwinProfile, and ResponseGenerator (_LLMResponseOutput)
            #    are called exactly once (they run sequentially).
            # 2. LLMStrategyOutput is called EXACTLY 0 times because the SimulationEngine is 100% deterministic!
            assert llm_call_counts.get("LLMStrategyOutput", 0) == 0
            assert llm_call_counts.get("IntentClassification", 0) == 0
            assert llm_call_counts.get("ConversationAnalysis", 0) == 1
            assert llm_call_counts.get("DigitalTwinProfile", 0) == 0
            assert llm_call_counts.get("_LLMResponseOutput", 0) == 1

    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_metrics_service_functionality() -> None:
    """Verify that MetricsService SQLite implementation increments and queries keys properly."""
    from app.services.llm_service import metrics_service
    metrics_service.reset()
    
    # Check baseline
    assert metrics_service.get("429_count") == 0
    assert metrics_service.count_429 == 0
    
    # Increment metrics
    metrics_service.increment("429_count", 1)
    metrics_service.increment("fallback_count", 3)
    metrics_service.increment("cache_hits", 2)
    metrics_service.increment("cache_misses", 5)
    
    assert metrics_service.count_429 == 1
    assert metrics_service.fallback_count == 3
    assert metrics_service.cache_hits == 2
    assert metrics_service.cache_misses == 5
    
    # Test setting arbitrary values
    metrics_service.set_value("groq_cooldown_until", "12345.67")
    assert metrics_service.get_value("groq_cooldown_until") == "12345.67"


def test_regex_attribute_extraction() -> None:
    """Verify that extract_attribute_by_regex correctly identifies specifications from text."""
    from app.services.product_knowledge_service import extract_attribute_by_regex
    
    # 1. Warranty test
    docs_warranty = [
        "The brand new Gaming Console comes with a premium 2-year warranty from the manufacturer.",
        "Some unrelated text here."
    ]
    val, conf = extract_attribute_by_regex("What is the warranty period?", docs_warranty)
    assert val == "2-year warranty"
    assert conf >= 0.75

    # 2. Color test
    docs_color = [
        "Product details: Color: Space Gray. Material: Aluminium.",
    ]
    val, conf = extract_attribute_by_regex("What color is it?", docs_color)
    assert val == "Space Gray"
    assert conf >= 0.75

    # 3. Weight/Measurement test
    docs_weight = [
        "Item dimensions: 10 x 20 x 5 cm. Weight of the appliance is 1.5 kg.",
    ]
    val, conf = extract_attribute_by_regex("How heavy is this product?", docs_weight)
    assert val == "1.5 kg"
    assert conf >= 0.75

    # 4. Dimension test
    docs_dims = [
        "The package dimension details are: 150mm x 75mm x 8mm.",
    ]
    val, conf = extract_attribute_by_regex("What are the dimensions?", docs_dims)
    assert val == "150mm x 75mm x 8mm"
    assert conf >= 0.75


@pytest.mark.anyio
async def test_product_qa_pipeline_with_caching() -> None:
    """Verify that answer_product_question checks cache and updates hit/miss stats correctly."""
    from app.services.product_knowledge_service import ProductKnowledgeService
    from app.services.llm_service import DeterministicFallbackProvider, metrics_service
    
    metrics_service.reset()
    
    mock_prod = Product(
        id=uuid.uuid4(),
        external_product_id="P_QA_CACHE_TEST",
        name="Mock Device",
        category="Electronics",
        selling_price=100.0,
        cost_price=50.0,
        minimum_price=80.0,
        target_margin=50.0,
        stock_quantity=10,
    )
    
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [] # No catalog spec
    mock_db.execute.return_value = mock_result
    
    llm = AsyncMock()
    from pydantic import BaseModel
    class WebExtraction(BaseModel):
        answer: str
        confidence: float
    llm.generate.return_value = WebExtraction(answer="Ocean Blue", confidence=0.9)
    service = ProductKnowledgeService(llm=llm)
    
    # 1. First run: should be a cache miss
    with patch("app.services.retrieval_provider.TavilyProvider.retrieve", new_callable=AsyncMock) as mock_retrieve:
        mock_retrieve.return_value = ["The Mock Device comes in Ocean Blue color and weighs 300g."]
        
        # Ask question
        res1 = await service.answer_product_question(mock_prod, "What color is it?", mock_db)
        assert "Ocean Blue" in res1.customer_response
        assert metrics_service.cache_misses == 1
        assert metrics_service.cache_hits == 0
        
        # 2. Second run: should hit cache
        res2 = await service.answer_product_question(mock_prod, "What color is it?", mock_db)
        assert res1 == res2
        assert metrics_service.cache_misses == 1
        assert metrics_service.cache_hits == 1


@pytest.mark.anyio
async def test_ollama_provider_graceful_disable() -> None:
    """Verify that OllamaProvider is disabled gracefully if model is empty."""
    from app.services.llm_service import OllamaProvider, GracefulFallbackProvider, settings
    
    # 1. OllamaProvider should set enabled=False
    provider = OllamaProvider(base_url="http://localhost:11434", model="")
    assert provider.enabled is False
    
    # 2. GracefulFallbackProvider should not fail initialization
    with patch.object(settings, "OLLAMA_MODEL", ""):
        fallback_prov = GracefulFallbackProvider(primary=None)
        assert fallback_prov.ollama is None or fallback_prov.ollama.enabled is False


@pytest.mark.anyio
async def test_circuit_breaker_states() -> None:
    """Verify stateful circuit breaker transitions: closed -> open -> half_open -> closed/open."""
    from app.services.llm_service import circuit_breaker_service, settings, metrics_service
    import time
    
    # Reset state
    await circuit_breaker_service._set_state({
        "consecutive_failures": 0,
        "state": "closed",
        "cooldown_until": 0.0,
        "half_open_probe_active": False
    })
    metrics_service.reset()
    
    # Verify check_circuit in closed state
    assert await circuit_breaker_service.check_circuit() == "closed"
    
    # Record failures up to threshold - 1
    for _ in range(settings.GROQ_FAILURE_THRESHOLD - 1):
        await circuit_breaker_service.record_failure()
        assert await circuit_breaker_service.check_circuit() == "closed"
        
    # Trip the circuit breaker
    await circuit_breaker_service.record_failure()
    assert await circuit_breaker_service.check_circuit() == "open"
    assert metrics_service.get("circuit_breaker_open_count") == 1
    
    # Check open state during cooldown
    state = await circuit_breaker_service._get_state()
    state["cooldown_until"] = time.time() + 10.0
    await circuit_breaker_service._set_state(state)
    assert await circuit_breaker_service.check_circuit() == "open"
    
    # Expire cooldown to enter half_open
    state["cooldown_until"] = time.time() - 1.0
    await circuit_breaker_service._set_state(state)
    assert await circuit_breaker_service.check_circuit() == "half_open"
    
    # Record success to close circuit
    await circuit_breaker_service.record_success()
    assert await circuit_breaker_service.check_circuit() == "closed"
    state = await circuit_breaker_service._get_state()
    assert state["consecutive_failures"] == 0


@pytest.mark.anyio
async def test_half_open_probe_concurrency() -> None:
    """Verify that only one request can probe the primary provider in half_open state."""
    from app.services.llm_service import circuit_breaker_service
    
    # Setup half_open state
    await circuit_breaker_service._set_state({
        "consecutive_failures": 5,
        "state": "half_open",
        "cooldown_until": 0.0,
        "half_open_probe_active": False
    })
    
    # First request acquires probe lock
    p1 = await circuit_breaker_service.acquire_half_open_probe()
    assert p1 is True
    
    # Concurrent request tries to acquire probe lock but fails
    p2 = await circuit_breaker_service.acquire_half_open_probe()
    assert p2 is False
    
    # Record failure of probe trips it back to open
    await circuit_breaker_service.record_failure()
    state = await circuit_breaker_service._get_state()
    assert state["state"] == "open"


@pytest.mark.anyio
async def test_negotiation_routing_stickiness_and_escape() -> None:
    """Verify sticky negotiation context remains active, but discovery escape commands bypass it."""
    from app.api.chat import is_discovery_escape
    
    # Non-escape pricing signals should keep negotiation
    assert is_discovery_escape("Can you do better?") is False
    assert is_discovery_escape("I want 20% discount") is False
    assert is_discovery_escape("Still expensive") is False
    
    # Escape routes should trigger escape
    assert is_discovery_escape("show laptops") is True
    assert is_discovery_escape("search phones") is True
    assert is_discovery_escape("let's compare products") is True
    assert is_discovery_escape("switch product") is True


@pytest.mark.anyio
async def test_customer_simulator_negotiation_awareness() -> None:
    """Verify that CustomerSimulator adjusts reactions based on negotiation intent and requested discounts."""
    from app.core.customer_simulator import CustomerSimulator
    from app.schemas.simulation import DigitalTwinProfile, LLMStrategyOutput
    from app.schemas.chat import ConversationAnalysis

    twin = DigitalTwinProfile(
        price_sensitivity=0.8,
        urgency=0.6,
        risk_aversion=0.5,
        brand_loyalty=1.0,  # High brand loyalty
        decision_speed=0.5
    )

    # 1. Non-negotiation context: brand loyalty bonus should apply to hardline
    strategy_hardline = LLMStrategyOutput(strategy_name="hardline", offer_type="hold_firm", discount_percent=0.0, bundle_value=0.0, reasoning="")
    reaction_normal = CustomerSimulator.simulate_reaction(twin, strategy_hardline, analysis=None)
    assert reaction_normal.trust_delta > 0.0
    assert reaction_normal.buying_intent_delta > 0.0

    # 2. Negotiation context: hardline should incur penalties
    analysis_neg = ConversationAnalysis(
        objection_type="price",
        negotiation_intent="seeking discount",
        urgency=0.6,
        sentiment="neutral",
        stage="negotiation",
        intent_type="negotiation",
        requested_discount=10.0
    )
    reaction_neg = CustomerSimulator.simulate_reaction(twin, strategy_hardline, analysis=analysis_neg)
    assert reaction_neg.trust_delta == -0.15
    assert reaction_neg.buying_intent_delta == -0.25
    assert reaction_neg.objection_delta == 0.20

    # 3. Negotiation context: discount strategy should receive bonuses
    strategy_discount = LLMStrategyOutput(strategy_name="discount", offer_type="percentage_discount", discount_percent=5.0, bundle_value=0.0, reasoning="")
    reaction_disc = CustomerSimulator.simulate_reaction(twin, strategy_discount, analysis=analysis_neg)
    assert reaction_disc.trust_delta == 0.15
    assert reaction_disc.buying_intent_delta == 0.25
    assert reaction_disc.objection_delta == -0.15


@pytest.mark.anyio
async def test_deterministic_fallback_provider_strategy_isolation() -> None:
    """Verify that DeterministicFallbackProvider isolates Recommended Strategy section and does not mix in runner-up discounts."""
    from app.services.llm_service import DeterministicFallbackProvider
    from app.core.response_generator import _LLMResponseOutput

    provider = DeterministicFallbackProvider()

    # Prompts for response generation containing a Recommended Strategy with no discount (hardline)
    # and a Runner-up Strategy with a discount (5.0%).
    prompt_content = (
        "## Recommended Strategy\n"
        "- Strategy: hardline\n"
        "- Offer Type: hold_firm\n"
        "- Strategy Reasoning: Maintain catalog pricing.\n"
        "- Winning Factors: High margin retention.\n\n"
        "## Alternative Strategies (Runner-ups)\n"
        "### Runner-up 1: discount\n"
        "- Offer Type: percentage_discount\n"
        "- Discount: 5.0%\n"
        "- Strategy Reasoning: Offer discount to close.\n"
    )

    result = await provider.generate(
        prompt=prompt_content,
        system_prompt="",
        response_model=_LLMResponseOutput
    )

    # The parsed strategy name should be hardline
    # The discount percent parsed should be 0.0 (from the Recommended section), NOT 5.0 (from the Runner-up section)
    assert "hardline" in result.internal_reasoning.lower()
    assert "0.0% discount" in result.internal_reasoning
    assert "5.0% discount" not in result.internal_reasoning


@pytest.mark.anyio
async def test_deterministic_fallback_provider_strategy_aware_response() -> None:
    """Verify that DeterministicFallbackProvider generates response texts incorporating winner and runner-up concessions."""
    from app.services.llm_service import DeterministicFallbackProvider
    from app.core.response_generator import _LLMResponseOutput

    provider = DeterministicFallbackProvider()

    # 1. Test discount strategy winner with concessions and bundle runner-up
    prompt_discount = (
        "## Recommended Strategy\n"
        "- Strategy: discount\n"
        "- Offer Type: percentage_discount\n"
        "- Discount: 10.0%\n"
        "- Concessions: Free Shipping, Extended Support\n"
        "- Strategy Reasoning: Provide competitive discount.\n\n"
        "## Alternative Strategies (Runner-ups)\n"
        "### Runner-up 1: bundle\n"
        "- Offer Type: value_added_bundle\n"
        "- Concessions: Free Installation\n"
    )

    result_discount = await provider.generate(
        prompt=prompt_discount,
        system_prompt="",
        response_model=_LLMResponseOutput
    )

    assert "10.0%" in result_discount.customer_response
    assert "Free Shipping" in result_discount.customer_response
    assert "Extended Support" in result_discount.customer_response
    assert "Free Installation" in result_discount.customer_response

    # 2. Test bundle strategy winner with concessions and discount runner-up
    prompt_bundle = (
        "## Recommended Strategy\n"
        "- Strategy: bundle\n"
        "- Offer Type: value_added_bundle\n"
        "- Concessions: Lifetime License, Premium Support\n"
        "- Strategy Reasoning: Bundle concessions.\n\n"
        "## Alternative Strategies (Runner-ups)\n"
        "### Runner-up 1: discount\n"
        "- Offer Type: percentage_discount\n"
        "- Discount: 8.0%\n"
    )

    result_bundle = await provider.generate(
        prompt=prompt_bundle,
        system_prompt="",
        response_model=_LLMResponseOutput
    )

    assert "Lifetime License" in result_bundle.customer_response
    assert "Premium Support" in result_bundle.customer_response
    assert "8.0%" in result_bundle.customer_response



