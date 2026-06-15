"""Re-export LLMProvider from the canonical llm_service module.

This module exists so that core business-logic modules can import
``from app.services.llm.base import LLMProvider`` with a clean,
package-oriented path while the full provider implementations remain
in :mod:`app.services.llm_service`.
"""

from __future__ import annotations

from app.services.llm_service import LLMProvider

__all__ = ["LLMProvider"]
