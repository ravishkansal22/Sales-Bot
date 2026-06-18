"""Product Pydantic schemas.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class ProductSchema(BaseModel):
    """Pydantic schema for catalog Product serialization.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    external_product_id: str
    name: str
    category: str
    description: str | None = None
    selling_price: float
    cost_price: float
    minimum_price: float
    target_margin: float
    stock_quantity: int
    popularity_index: float
    return_rate: float
    created_at: datetime | None = None
    updated_at: datetime | None = None
