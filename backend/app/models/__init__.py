"""Models package – imports all ORM models for Alembic auto-discovery.

When Alembic's ``env.py`` imports ``app.models``, every model class is
registered on :attr:`Base.metadata`, enabling ``--autogenerate`` to
detect schema changes.
"""

from __future__ import annotations

from app.models.conversation import Conversation
from app.models.customer import Customer, DigitalTwinSnapshot
from app.models.simulation import SimulationResult
from app.models.product import Product
from app.models.order import Order
from app.models.negotiation_context import NegotiationContext
from app.models.product_specification import ProductSpecification
from app.models.locked_deal import LockedDeal

__all__ = [
    "Conversation",
    "Customer",
    "DigitalTwinSnapshot",
    "SimulationResult",
    "Product",
    "Order",
    "NegotiationContext",
    "ProductSpecification",
    "LockedDeal",
]
