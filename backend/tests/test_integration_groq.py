from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from pydantic import BaseModel, Field

from app.services.llm_service import GroqProvider
from app.services.product_knowledge_service import ProductKnowledgeService
from app.core.intent_classifier import IntentClassification
from app.core.simulation_engine import SimulationEngine
from app.core.strategies.registry import StrategyRegistry
from app.schemas.simulation import LLMStrategyOutput, DigitalTwinProfile
from app.schemas.chat import ConversationAnalysis
from app.models.product import Product

class DummyResponse(BaseModel):
    value: int
    name: str

@pytest.mark.asyncio
async def test_text_answer_bypass_json_mode() -> None:
    """Verify that TextAnswer bypasses JSON mode and doesn't pass response_format."""
    provider = GroqProvider(api_key="test_key", model="llama-3.3-70b-versatile")
    
    class TextAnswer(BaseModel):
        answer: str

    mock_completion = MagicMock()
    mock_completion.choices = [
        MagicMock(message=MagicMock(content="This is a plain text answer."))
    ]
    
    with patch.object(provider._client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_completion
        
        res = await provider.generate(
            prompt="Tell me about the product",
            system_prompt="Be helpful",
            response_model=TextAnswer
        )
        
        assert isinstance(res, TextAnswer)
        assert res.answer == "This is a plain text answer."
        
        # Verify that response_format was NOT passed in completions.create
        called_kwargs = mock_create.call_args[1]
        assert "response_format" not in called_kwargs


@pytest.mark.asyncio
async def test_markdown_block_stripping() -> None:
    """Verify that markdown code blocks are cleaned and parsed correctly."""
    provider = GroqProvider(api_key="test_key", model="llama-3.3-70b-versatile")
    
    mock_completion = MagicMock()
    mock_completion.choices = [
        MagicMock(message=MagicMock(content='```json\n{"value": 42, "name": "cleaned_json"}\n```'))
    ]
    
    with patch.object(provider._client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_completion
        
        res = await provider.generate(
            prompt="Give me json",
            system_prompt="Test",
            response_model=DummyResponse
        )
        
        assert res.value == 42
        assert res.name == "cleaned_json"


@pytest.mark.asyncio
async def test_model_specific_repair_intent_classification() -> None:
    """Verify that a schema violation for IntentClassification is repaired to model-specific defaults."""
    provider = GroqProvider(api_key="test_key", model="llama-3.3-70b-versatile")
    
    # Missing required fields: 'confidence' and 'reasoning'
    mock_completion = MagicMock()
    mock_completion.choices = [
        MagicMock(message=MagicMock(content='{"intent": "product_discovery"}'))
    ]
    
    with patch.object(provider._client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_completion
        
        res = await provider.generate(
            prompt="Search vacuum",
            system_prompt="Test",
            response_model=IntentClassification
        )
        
        assert res.intent == "product_discovery"
        # Repaired fields
        assert res.confidence == 0.95
        assert res.reasoning == "Schema repair"
        assert res.target_product_ids == []


@pytest.mark.asyncio
async def test_model_specific_repair_invalid_field_type() -> None:
    """Verify that an invalid field type is repaired via the 2-pass repair loop."""
    provider = GroqProvider(api_key="test_key", model="llama-3.3-70b-versatile")
    
    # 'confidence' is provided but is a non-float string, which triggers validation error
    mock_completion = MagicMock()
    mock_completion.choices = [
        MagicMock(message=MagicMock(content='{"intent": "general", "confidence": "high", "reasoning": "Greetings"}'))
    ]
    
    with patch.object(provider._client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_completion
        
        res = await provider.generate(
            prompt="Hello",
            system_prompt="Test",
            response_model=IntentClassification
        )
        
        assert res.intent == "general"
        assert res.reasoning == "Greetings"
        # Invalid confidence string repaired to default
        assert res.confidence == 0.95


@pytest.mark.asyncio
async def test_missing_specifications_handling() -> None:
    """Verify that product question QA returns Specification Unavailable or General Knowledge Estimate based on confidence."""
    from app.services.product_knowledge_service import GeneralKnowledgeEstimate
    
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value=GeneralKnowledgeEstimate(
        answer="standard black",
        confidence=0.3,
        reasoning="Inconclusive standards"
    ))
    service = ProductKnowledgeService(llm=mock_llm)
    
    product = Product(
        id="d77f32fb-145e-4c1b-959a-60e557f5a31d",
        name="LG Vacuum Pro",
        category="Home Appliances",
        selling_price=18500.0,
        cost_price=12000.0,
        minimum_price=15000.0,
        stock_quantity=50,
        popularity_index=80.0,
        return_rate=2.5,
    )
    
    mock_db = AsyncMock()
    # Mocking executing select returns empty list of specs
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result
    
    # 1. Low confidence case
    response = await service.answer_product_question(product, "What is the color of this vacuum cleaner?", mock_db)
    
    assert "unavailable" in response.customer_response.lower()
    assert "LG Vacuum Pro" in response.customer_response
    assert response.source == "none"
    mock_llm.generate.assert_called_once()
    
    # 2. High confidence case
    mock_llm.generate.reset_mock()
    mock_llm.generate.return_value = GeneralKnowledgeEstimate(
        answer="White and Chrome",
        confidence=0.75,
        reasoning="Standard appliance color schemes"
    )
    # Clear cache to allow a new execution
    if hasattr(ProductKnowledgeService, "_in_memory_cache"):
        ProductKnowledgeService._in_memory_cache.clear()
        
    response2 = await service.answer_product_question(product, "What is the color of this vacuum cleaner?", mock_db)
    assert response2.source == "general_knowledge"
    assert "White and Chrome" in response2.customer_response
    assert "Disclaimer: This is an estimate" in response2.internal_notes
    mock_llm.generate.assert_called_once()


def test_safety_bounds_clamping_simulation_engine() -> None:
    """Verify that strategy min bounds are clamped by max bounds if they conflict."""
    engine = SimulationEngine(llm=MagicMock(), registry=StrategyRegistry())
    
    # Out of bounds LLM strategy output where min_discount_percent is 5% in DiscountStrategy,
    # but the dynamic maximum ceiling is clamped to 3.0% (due to critical stock, segment, etc.)
    output = LLMStrategyOutput(
        strategy_name="discount",
        offer_type="percentage_discount",
        discount_percent=12.0,
        bundle_value=0.0,
        reasoning="Offer discount",
    )
    
    # max_discount_percent is 3.0%, min_discount_percent is 5.0%
    constraints = {
        "min_discount_percent": 5.0,
        "max_discount_percent": 3.0,
        "min_bundle_value": 0.0,
        "max_bundle_value": 0.0
    }
    
    clamped = engine._clamp_output(output, constraints, deal_value=10000.0)
    
    # Discount percent should be clamped to max_discount_percent (3.0%), not the strategy's minimum (5.0%)
    assert clamped.discount_percent == 3.0
