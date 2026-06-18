#!/usr/bin/env python3
"""Ingest customers and orders from raw amazon CSV dataset into PostgreSQL.

Aggregates stats for customers, resolves product foreign keys (dynamically
creating products that don't exist in the catalog), and bulk inserts.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import os
import random
import sys
import uuid
from datetime import UTC, datetime

# Resolve project root to allow imports from app
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from sqlalchemy import delete, select
from app.db.base import get_engine, get_session_factory
from app.models.customer import Customer
from app.models.order import Order
from app.models.product import Product
from app.services.llm_service import settings

# Seed for reproducibility
random.seed(42)


async def ingest_customers(csv_path: str, limit: int, truncate: bool) -> None:
    """Ingest customers and orders from CSV into database.

    Args:
        csv_path: Path to amazon_dataset.csv.
        limit: Max number of customers to ingest.
        truncate: Truncate existing customer and order records first.
    """
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found at {csv_path}", file=sys.stderr)
        return

    engine = get_engine(settings.DATABASE_URL)
    session_factory = get_session_factory(engine)

    async with session_factory() as session:
        if truncate:
            print("Truncating orders and customers tables...")
            await session.execute(delete(Order))
            await session.execute(delete(Customer))
            await session.commit()

        # 1. Fetch all existing product mappings: external_product_id -> UUID
        print("Loading product mappings from database...")
        prod_result = await session.execute(select(Product.id, Product.external_product_id))
        products_map: dict[str, uuid.UUID] = {row[1]: row[0] for row in prod_result.all()}
        print(f"Loaded {len(products_map)} products from database.")

        # 2. Parse CSV to aggregate customer transactions and create missing products
        print(f"Reading CSV from {csv_path}...")
        customer_orders: dict[str, list[dict]] = {}
        new_products_to_insert: dict[str, Product] = {}

        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                user_id = row.get("user_id")
                prod_id = row.get("product_id")
                
                if not user_id or not prod_id:
                    continue

                try:
                    price = float(row.get("price", 0.0))
                    final_price = float(row.get("final_price", 0.0))
                    discount = float(row.get("discount", 0.0))
                    raw_date = row.get("purchase_date")
                    purchase_date = datetime.strptime(raw_date, "%Y-%m-%d").replace(tzinfo=UTC) if raw_date else datetime.now(UTC)
                    payment_method = row.get("payment_method", "Other")
                    
                    is_returned = row.get("is_returned", "False").lower() == "true"
                    delivery_status = "Returned" if is_returned else row.get("delivery_status", "Delivered")
                except (ValueError, TypeError) as e:
                    # Skip malformed order
                    continue

                # If product doesn't exist in DB, create it dynamically from the order product metadata
                if prod_id not in products_map and prod_id not in new_products_to_insert:
                    prod_uuid = uuid.uuid4()
                    
                    # Generate product constraints
                    margin_percent = random.uniform(0.20, 0.40)
                    cost_price = price * (1.0 - margin_percent)
                    minimum_price = cost_price * 1.15
                    target_margin = margin_percent
                    
                    brand = row.get("brand", "Generic")
                    subcategory = row.get("subcategory", "Item")
                    category = row.get("category", "General")
                    stock = int(row.get("stock", 50))
                    rating = float(row.get("rating", 4.0))

                    new_products_to_insert[prod_id] = Product(
                        id=prod_uuid,
                        external_product_id=prod_id,
                        name=f"{brand} {subcategory}",
                        category=category,
                        description=f"Purchase history catalog item: {brand} {subcategory}.",
                        selling_price=round(price, 2),
                        cost_price=round(cost_price, 2),
                        minimum_price=round(minimum_price, 2),
                        target_margin=round(target_margin, 4),
                        stock_quantity=stock,
                        popularity_index=rating,
                        return_rate=round(random.uniform(1.0, 10.0), 2),
                    )
                    products_map[prod_id] = prod_uuid

                if user_id not in customer_orders:
                    # Limit check
                    if len(customer_orders) >= limit:
                        continue
                    customer_orders[user_id] = []

                customer_orders[user_id].append({
                    "product_id_str": prod_id,
                    "purchase_price": final_price,
                    "discount_percent": discount,
                    "purchase_date": purchase_date,
                    "payment_method": payment_method,
                    "delivery_status": delivery_status,
                })

        # 3. Insert new products first to prevent FK constraint failures
        if new_products_to_insert:
            print(f"Dynamically inserting {len(new_products_to_insert)} products referenced in orders...")
            new_products_list = list(new_products_to_insert.values())
            chunk_size = 2000
            for i in range(0, len(new_products_list), chunk_size):
                chunk = new_products_list[i : i + chunk_size]
                session.add_all(chunk)
                await session.flush()
                print(f"Inserted dynamic product chunk {i // chunk_size + 1}: {len(chunk)} items.")

        # 4. Create customers database objects
        print(f"Aggregating profiles for {len(customer_orders)} customers...")
        customers_to_insert: list[Customer] = []
        customer_uuid_map: dict[str, uuid.UUID] = {}

        for user_id, orders_list in customer_orders.items():
            cust_uuid = uuid.uuid4()
            customer_uuid_map[user_id] = cust_uuid

            total_spend = sum(o["purchase_price"] for o in orders_list)
            total_orders = len(orders_list)
            avg_order = total_spend / total_orders if total_orders > 0 else 0.0
            last_purchase = max(o["purchase_date"] for o in orders_list)

            # Determine segment based on behavior
            returned_count = sum(1 for o in orders_list if o["delivery_status"] == "Returned")
            return_rate = returned_count / total_orders if total_orders > 0 else 0.0
            
            discounted_count = sum(1 for o in orders_list if o["discount_percent"] > 15.0)
            discount_ratio = discounted_count / total_orders if total_orders > 0 else 0.0

            if total_spend > 25000 or total_orders > 8:
                segment = "VIP"
            elif return_rate > 0.25:
                segment = "High Returner"
            elif discount_ratio > 0.50:
                segment = "Bargain Hunter"
            else:
                segment = "Standard"

            customers_to_insert.append(
                Customer(
                    id=cust_uuid,
                    external_customer_id=user_id,
                    customer_segment=segment,
                    total_spend=round(total_spend, 2),
                    average_order_value=round(avg_order, 2),
                    total_orders=total_orders,
                    last_purchase_date=last_purchase,
                    name=f"Customer {user_id}",
                    email=f"{user_id.lower()}@example.com",
                    metadata_={"ingested": True},
                )
            )

        # Bulk insert customers
        chunk_size = 2000
        for i in range(0, len(customers_to_insert), chunk_size):
            chunk = customers_to_insert[i : i + chunk_size]
            session.add_all(chunk)
            await session.flush()
            print(f"Inserted customer chunk {i // chunk_size + 1}: {len(chunk)} profiles.")

        # 5. Map and create order records
        orders_to_insert: list[Order] = []
        for user_id, orders_list in customer_orders.items():
            cust_uuid = customer_uuid_map[user_id]
            for o in orders_list:
                orders_to_insert.append(
                    Order(
                        id=uuid.uuid4(),
                        customer_id=cust_uuid,
                        product_id=products_map[o["product_id_str"]],
                        purchase_price=round(o["purchase_price"], 2),
                        purchase_date=o["purchase_date"],
                        payment_method=o["payment_method"],
                        delivery_status=o["delivery_status"],
                    )
                )

        # Bulk insert orders
        print(f"Inserting {len(orders_to_insert)} transaction orders...")
        for i in range(0, len(orders_to_insert), chunk_size):
            chunk = orders_to_insert[i : i + chunk_size]
            session.add_all(chunk)
            await session.flush()
            print(f"Inserted order chunk {i // chunk_size + 1}: {len(chunk)} transactions.")

        await session.commit()
        print("Customer and order history ingestion complete!")

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest customers and orders into Ghost Negotiator database.")
    parser.add_argument(
        "--csv",
        type=str,
        default=os.path.join(PROJECT_ROOT, "data", "raw", "amazon_dataset.csv"),
        help="Path to amazon_dataset.csv",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10000,
        help="Max number of customers to ingest (default: 10000)",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Delete existing customer and order records before ingesting",
    )

    args = parser.parse_args()

    asyncio.run(ingest_customers(args.csv, args.limit, args.truncate))


if __name__ == "__main__":
    main()
