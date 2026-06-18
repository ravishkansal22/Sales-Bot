#!/usr/bin/env python3
"""Ingest products from raw ecommerce CSV dataset into PostgreSQL.

Deduplicates products, cleans fields, generates cost and minimum prices,
and bulk inserts into the products table.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import os
import random
import sys
import uuid
from datetime import datetime

# Resolve project root to allow imports from app
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from sqlalchemy import delete
from app.db.base import get_engine, get_session_factory
from app.models.product import Product
from app.services.llm_service import settings

# Seed random number generator for reproducible business metrics
random.seed(42)


async def ingest_products(csv_path: str, limit: int, truncate: bool) -> None:
    """Ingest products from CSV into database.

    Args:
        csv_path: Path to ecommerce_dataset.csv.
        limit: Max number of unique products to ingest.
        truncate: Truncate existing records in table before starting.
    """
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found at {csv_path}", file=sys.stderr)
        return

    engine = get_engine(settings.DATABASE_URL)
    session_factory = get_session_factory(engine)

    async with session_factory() as session:
        if truncate:
            print("Truncating products table...")
            await session.execute(delete(Product))
            await session.commit()

        print(f"Reading CSV from {csv_path}...")
        unique_products: dict[str, dict] = {}

        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ext_id = row.get("Product ID")
                if not ext_id:
                    continue

                if ext_id in unique_products:
                    continue

                try:
                    selling_price = float(row.get("Price", 0.0))
                    stock_quantity = int(row.get("Stock Level", 0))
                    popularity_index = float(row.get("Popularity Index", 0.0))
                    return_rate = float(row.get("Return Rate", 0.0))
                    name = row.get("Product Name", "Unnamed Product")
                    category = row.get("Category", "General")
                except (ValueError, TypeError) as e:
                    # Skip rows with malformed numeric data
                    continue

                # Generate target margin and cost bounds
                margin_percent = random.uniform(0.20, 0.40)
                cost_price = selling_price * (1.0 - margin_percent)
                minimum_price = cost_price * 1.15
                target_margin = margin_percent

                unique_products[ext_id] = {
                    "id": uuid.uuid4(),
                    "external_product_id": ext_id,
                    "name": name,
                    "category": category,
                    "description": f"High-quality {name} in {category} category.",
                    "selling_price": round(selling_price, 2),
                    "cost_price": round(cost_price, 2),
                    "minimum_price": round(minimum_price, 2),
                    "target_margin": round(target_margin, 4),
                    "stock_quantity": stock_quantity,
                    "popularity_index": popularity_index,
                    "return_rate": return_rate,
                }

                if len(unique_products) >= limit:
                    break

        print(f"Found {len(unique_products)} unique products to insert.")
        
        # Batch insert to DB
        products_to_insert = [Product(**p) for p in unique_products.values()]
        
        # Insert in chunks of 2000
        chunk_size = 2000
        for i in range(0, len(products_to_insert), chunk_size):
            chunk = products_to_insert[i : i + chunk_size]
            session.add_all(chunk)
            await session.flush()
            print(f"Inserted chunk {i // chunk_size + 1}: {len(chunk)} items.")

        await session.commit()
        print("Product catalog ingestion complete!")

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest products into Ghost Negotiator database.")
    parser.add_argument(
        "--csv",
        type=str,
        default=os.path.join(PROJECT_ROOT, "data", "raw", "ecommerce_dataset.csv"),
        help="Path to ecommerce_dataset.csv",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10000,
        help="Max number of unique products to ingest (default: 10000)",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Delete existing products from database before ingesting",
    )

    args = parser.parse_args()

    asyncio.run(ingest_products(args.csv, args.limit, args.truncate))


if __name__ == "__main__":
    main()
