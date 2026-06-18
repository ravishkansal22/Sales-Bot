"""Integration tests for the API endpoints of Ghost Negotiator.

Mocks the LLM calls, SQLAlchemy database session, and app lifespan
events to verify that the endpoints successfully process requests.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.db.postgres import get_db
from app.main import app
from app.models.customer import Customer
from app.services.llm.base import LLMProvider

# ---------------------------------------------------------------------------
# Mock LLM Provider
# ---------------------------------------------------------------------------

class MockLLMProvider(LLMProvider):
    """Mock LLM Provider that returns structured Pydantic objects."""

    async def generate(self, prompt: str, system_prompt: str, response_model: type[BaseModel]) -> BaseModel:
        # 1. Conversation Analysis
        if response_model.__name__ == "ConversationAnalysis":
            return response_model(
                objection_type="price",
                negotiation_intent="seeking discount",
                urgency=0.7,
                sentiment="neutral",
                stage="decision",
            )
        # 2. Digital Twin
        elif response_model.__name__ == "DigitalTwinProfile":
            return response_model(
                price_sensitivity=0.8,
                urgency=0.7,
                risk_aversion=0.5,
                brand_loyalty=0.4,
                decision_speed=0.6,
            )
        # 3. Strategy Output
        elif response_model.__name__ == "LLMStrategyOutput":
            strategy_name = "discount"
            offer_type = "discount"
            if "hardline" in prompt.lower():
                strategy_name = "hardline"
                offer_type = "hardline"
            elif "bundle" in prompt.lower():
                strategy_name = "bundle"
                offer_type = "bundle"
            elif "personalized" in prompt.lower():
                strategy_name = "personalized"
                offer_type = "personalized"

            return response_model(
                strategy_name=strategy_name,
                offer_type=offer_type,
                discount_percent=10.0,
                bundle_value=0.0,
                reasoning=f"Mock reasoning for {strategy_name}",
            )
        # 4. Response Generator Output
        elif "ResponseOutput" in response_model.__name__ or hasattr(response_model, "customer_response"):
            return response_model(
                customer_response="Thank you for your feedback. We can offer a special 10% discount.",
                internal_reasoning="Address price objection with discount.",
            )

        raise ValueError(f"Unknown response model in MockLLMProvider: {response_model}")


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

    # Mock async execute method
    db_session.execute = AsyncMock()

    # Mock scalar and scalars methods
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = None
    mock_result.scalars.return_value.all.return_value = []
    db_session.execute.return_value = mock_result

    # Mock flush, commit, rollback
    db_session.flush = AsyncMock()
    db_session.commit = AsyncMock()
    db_session.rollback = AsyncMock()

    return db_session


@pytest.fixture
def client(mock_db: MagicMock) -> TestClient:
    """Fixture for FastAPI TestClient with overridden db dependency."""
    # Override database dependency
    app.dependency_overrides[get_db] = lambda: mock_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# API Tests
# ---------------------------------------------------------------------------

@patch("app.api.chat.get_llm_provider")
def test_chat_endpoint(mock_get_llm: MagicMock, client: TestClient, mock_db: MagicMock) -> None:
    """Test the /chat endpoint using the mock LLM provider and mock database."""
    # Configure mock LLM provider
    mock_get_llm.return_value = MockLLMProvider()

    # Stub Customer search to return a mock customer
    mock_customer = Customer(
        id="cust_12345678",
        name="Customer cust_123",
        email="test@example.com",
        metadata_={},
    )

    # We setup db_session.execute mock to return the mock customer
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.side_effect = [mock_customer, None]  # First customer, then latest twin snapshot
    mock_result.scalars.return_value.all.return_value = []  # Empty history
    mock_db.execute.return_value = mock_result

    payload = {
        "message": "Hi, your product is too expensive. Can you offer a discount?",
        "customer_id": "cust_12345678",
        "deal_value": 12000.0,
        "cost_basis": 8000.0,
    }

    response = client.post("/api/v1/chat", json=payload)

    assert response.status_code == 200, response.text
    data = response.json()

    assert "response" in data
    assert "internal_reasoning" in data
    assert "digital_twin" in data
    assert "simulations" in data
    assert "winner" in data

    assert data["winner"]["winning_strategy"] is not None
    assert len(data["simulations"]) > 0
    assert "discount" in [s["strategy_name"] for s in data["simulations"]]


@patch("app.api.simulation.get_llm_provider")
def test_simulate_endpoint(mock_get_llm: MagicMock, client: TestClient, mock_db: MagicMock) -> None:
    """Test the /simulate endpoint using the mock LLM provider and mock database."""
    mock_get_llm.return_value = MockLLMProvider()

    mock_customer = Customer(
        id="cust_12345678",
        name="Customer cust_123",
        email="test@example.com",
        metadata_={},
    )

    mock_result = MagicMock()
    mock_result.scalars.return_value.first.side_effect = [mock_customer, None]
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    payload = {
        "message": "I am looking to buy 500 licenses but need a better rate.",
        "customer_id": "cust_12345678",
        "deal_value": 20000.0,
        "cost_basis": 12000.0,
    }

    response = client.post("/api/v1/simulate", json=payload)

    assert response.status_code == 200, response.text
    data = response.json()

    assert "digital_twin" in data
    assert "analysis" in data
    assert "simulations" in data
    assert "winner" in data

    assert data["analysis"]["objection_type"] == "price"
    assert len(data["simulations"]) > 0
