from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from pydantic import BaseModel

from app.services.llm_service import GroqProvider, get_llm_provider, get_settings, GracefulFallbackProvider

class MockResponseModel(BaseModel):
    name: str
    value: int

def test_groq_provider_init() -> None:
    provider = GroqProvider(api_key="test_key", model="llama-3.3-70b-versatile")
    assert provider._model == "llama-3.3-70b-versatile"
    assert provider._client is not None

@pytest.mark.asyncio
async def test_groq_provider_generate() -> None:
    provider = GroqProvider(api_key="test_key", model="llama-3.3-70b-versatile")
    
    mock_completion = MagicMock()
    mock_completion.choices = [
        MagicMock(message=MagicMock(content='{"name": "test_object", "value": 42}'))
    ]
    
    mock_create = AsyncMock(return_value=mock_completion)
    provider._client.chat.create = mock_create  # mock synchronous or direct client call
    
    # Patch the AsyncGroq client's create completion call
    with patch.object(provider._client.chat.completions, "create", new_callable=AsyncMock) as mock_create_comp:
        mock_create_comp.return_value = mock_completion
        
        res = await provider.generate(
            prompt="Hello",
            system_prompt="Test System",
            response_model=MockResponseModel
        )
        
        assert isinstance(res, MockResponseModel)
        assert res.name == "test_object"
        assert res.value == 42
        mock_create_comp.assert_called_once()


@pytest.mark.asyncio
async def test_groq_provider_generate_with_repair() -> None:
    provider = GroqProvider(api_key="test_key", model="llama-3.3-70b-versatile")
    
    # Simulate partial output missing 'value' field (which is required by MockResponseModel)
    mock_completion = MagicMock()
    mock_completion.choices = [
        MagicMock(message=MagicMock(content='{"name": "test_object_repaired"}'))
    ]
    
    with patch.object(provider._client.chat.completions, "create", new_callable=AsyncMock) as mock_create_comp:
        mock_create_comp.return_value = mock_completion
        
        res = await provider.generate(
            prompt="Hello",
            system_prompt="Test System",
            response_model=MockResponseModel
        )
        
        assert isinstance(res, MockResponseModel)
        assert res.name == "test_object_repaired"
        assert res.value == 0  # Repaired default value for integer
        mock_create_comp.assert_called_once()


def test_get_llm_provider_groq() -> None:
    settings = get_settings()
    
    # Override settings
    with patch.object(settings, "LLM_PROVIDER", "groq"), \
         patch.object(settings, "GROQ_API_KEY", "groq_api_key_123"), \
         patch.object(settings, "DEFAULT_MODEL", "llama-3.3-70b-versatile"):
        
        provider = get_llm_provider()
        assert isinstance(provider, GracefulFallbackProvider)
        assert isinstance(provider.primary, GroqProvider)
        assert provider.primary._model == "llama-3.3-70b-versatile"

def test_get_llm_provider_groq_fallback() -> None:
    settings = get_settings()
    
    # Override settings with empty API key
    with patch.object(settings, "LLM_PROVIDER", "groq"), \
         patch.object(settings, "GROQ_API_KEY", ""):
        
        provider = get_llm_provider()
        assert isinstance(provider, GracefulFallbackProvider)
        assert provider.primary is None
