from __future__ import annotations

import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.customer import Customer

class CustomerService:
    @staticmethod
    async def resolve_customer(db: AsyncSession, id_str: str) -> Customer | None:
        """Helper to resolve a customer from UUID or external customer ID string."""
        if not id_str:
            return None
        try:
            cust_uuid = uuid.UUID(id_str)
            result = await db.execute(select(Customer).where(Customer.id == cust_uuid))
            customer = result.scalars().first()
            if customer:
                return customer
        except ValueError:
            pass

        stmt = select(Customer).where(Customer.external_customer_id == id_str)
        result = await db.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def get_or_create_customer(db: AsyncSession, customer_id: str) -> Customer:
        """Get customer by ID or external ID, or create a new stub record."""
        customer = await CustomerService.resolve_customer(db, customer_id)
        if customer is not None:
            return customer

        # Determine if customer_id itself is a valid UUID to use as primary key
        try:
            cust_uuid = uuid.UUID(customer_id)
            external_id = None
        except ValueError:
            cust_uuid = uuid.uuid4()
            external_id = customer_id

        customer = Customer(
            id=cust_uuid,
            external_customer_id=external_id,
            name=f"Customer {customer_id[:8]}",
            email=None,
            metadata_={},
        )
        db.add(customer)
        await db.flush()
        return customer
