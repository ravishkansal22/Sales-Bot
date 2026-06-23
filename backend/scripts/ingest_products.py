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


def transform_product(ext_id: str, name: str, category: str, raw_price: float) -> dict:
    # We will use a deterministic hash of ext_id to pick a brand/model from lists
    import hashlib
    h = int(hashlib.md5(ext_id.encode('utf-8')).hexdigest(), 16)
    
    # Define brand lists
    smartphones = [
        ("iPhone 17 Pro", 129900.0),
        ("Galaxy S25 Ultra", 109999.0),
        ("Pixel 9 Pro", 99999.0),
        ("OnePlus 13", 64999.0),
        ("Xiaomi 15 Pro", 79999.0),
        ("iPhone 16", 79900.0),
        ("Galaxy A55", 39999.0),
        ("Redmi Note 13", 19999.0)
    ]
    
    laptops = [
        ("ThinkPad X1 Carbon", 145000.0),
        ("MacBook Pro 16", 249900.0),
        ("Dell XPS 15", 185000.0),
        ("ASUS ROG Zephyrus", 159999.0),
        ("HP EliteBook Ultra", 125000.0),
        ("Lenovo IdeaPad Slim", 45990.0),
        ("Acer Aspire 5", 35990.0)
    ]
    
    monitors = [
        ("LG UltraFine 5K", 95000.0),
        ("Samsung Odyssey G9", 99000.0),  # Adjusted to fit under 100k
        ("Dell UltraSharp 32", 75000.0),
        ("ASUS ProArt Display", 55000.0),
        ("BenQ PD3220U", 85000.0),
        ("Acer Nitro 27", 14999.0),
        ("LG QuadHD 24", 11999.0)
    ]
    
    tvs = [
        ("Sony BRAVIA XR OLED", 249900.0),
        ("LG C4 OLED TV", 189900.0),
        ("Samsung Neo QLED 8K", 349900.0),
        ("TCL QM8 mini-LED", 89990.0),
        ("Sony A95L QD-OLED", 419900.0),
        ("Xiaomi Smart TV 55", 34999.0),
        ("OnePlus TV 43", 22999.0)
    ]
    
    headphones = [
        ("Sony WH-1000XM5", 29990.0),
        ("Bose QuietComfort Ultra", 35900.0),
        ("Sennheiser Momentum 4", 28990.0),
        ("AirPods Max", 49900.0),  # Adjusted to fit under 50k
        ("Audio-Technica M50x", 12999.0),
        ("Sony WF-1000XM5", 19990.0),
        ("JBL Tune 760NC", 5999.0),
        ("boAt Rockerz 450", 1499.0)
    ]
    
    vacuums = [
        ("LG Vacuum Pro", 18500.0),
        ("Dyson V15 Detect", 35900.0),  # Adjusted to fit under 40k
        ("Shark Stratos Cordless", 38900.0),
        ("Miele Complete C3", 32900.0),  # Adjusted to fit under 40k
        ("iRobot Roomba J9+", 39900.0),   # Adjusted to fit under 40k
        ("Eureka Forbes DX1150", 8999.0),
        ("Kent Zoom Vacuum", 6999.0)
    ]
    
    refrigerators = [
        ("Samsung Family Hub Refrigerator", 165000.0),
        ("LG InstaView Refrigerator", 189900.0),
        ("Bosch 800 Series Refrigerator", 145000.0),
        ("Whirlpool French Door Fridge", 85000.0),
        ("Haier Double Door Refrigerator", 24999.0),
        ("Godrej Single Door Refrigerator", 15900.0)  # Adjusted to fit above 15k
    ]

    name_lower = name.lower()
    new_name = name
    price = raw_price
    
    # Match specific product classes
    if category == "Electronics":
        if "phone" in name_lower or "mobile" in name_lower or name_lower == "smartphone":
            model, price = smartphones[h % len(smartphones)]
            new_name = model
        elif "laptop" in name_lower or "notebook" in name_lower:
            model, price = laptops[h % len(laptops)]
            new_name = model
        elif "monitor" in name_lower or "screen" in name_lower:
            model, price = monitors[h % len(monitors)]
            new_name = model
        elif "tv" in name_lower or "television" in name_lower:
            model, price = tvs[h % len(tvs)]
            new_name = model
        elif "headphone" in name_lower or "earbud" in name_lower or "audio" in name_lower or name_lower == "headphones":
            model, price = headphones[h % len(headphones)]
            new_name = model
        else:
            brands = ["Sony", "Canon", "Apple", "Samsung", "Garmin", "Sonos"]
            brand = brands[h % len(brands)]
            new_name = f"{brand} {name} Pro"
            price = 8000.0 + (raw_price % 72000.0)
            
    elif category == "Home Appliances":
        if "vacuum" in name_lower or "cleaner" in name_lower:
            model, price = vacuums[h % len(vacuums)]
            new_name = model
        elif "fridge" in name_lower or "refrigerator" in name_lower:
            model, price = refrigerators[h % len(refrigerators)]
            new_name = model
        else:
            brands = ["Bosch", "LG", "Dyson", "KitchenAid", "Breville", "Whirlpool", "Siemens"]
            brand = brands[h % len(brands)]
            new_name = f"{brand} {name} Pro"
            price = 12000.0 + (raw_price % 78000.0)
            
    elif category == "Apparel":
        brands = ["Patagonia", "Levi's", "Hugo Boss", "Ralph Lauren", "Arc'teryx", "Columbia"]
        brand = brands[h % len(brands)]
        new_name = f"{brand} Premium {name}"
        price = 2500.0 + (raw_price % 15500.0)
        
    elif category == "Footwear":
        brands = ["Nike Air Max", "Adidas Ultraboost", "Timberland Pro", "Christian Louboutin", "Birkenstock", "Puma Pro"]
        brand = brands[h % len(brands)]
        new_name = f"{brand} {name}"
        price = 3000.0 + (raw_price % 22000.0)
        
    elif category == "Books":
        titles = {
            "fiction": [
                "The Great Gatsby (Collector's Edition)",
                "To Kill a Mockingbird (B2B Library Ed.)",
                "1984 (Hardcover Premium)",
                "The Hobbit (Special Illustrated Ed.)"
            ],
            "non-fiction": [
                "Designing Data-Intensive Applications",
                "Introduction to Algorithms (CLRS)",
                "Clean Code: A Handbook of Agile Software Craftsmanship",
                "Thinking, Fast and Slow (B2B Library Ed.)"
            ],
            "cookbooks": [
                "The Professional Chef (9th Edition)",
                "Salt, Fat, Acid, Heat (Premium Ed.)",
                "Modernist Cuisine at Home",
                "Flour Water Salt Yeast"
            ],
            "comics": [
                "Watchmen (Deluxe Edition)",
                "Batman: The Dark Knight Returns",
                "The Sandman Omnibus Vol 1",
                "Maus: A Survivor's Tale"
            ],
            "textbooks": [
                "Corporate Finance (13th Edition)",
                "Principles of Economics (Mankiw)",
                "Marketing Management (Kotler)",
                "Organizational Behavior (Robbins)"
            ]
        }
        matched_cat = "non-fiction"
        for k in titles.keys():
            if k in name_lower:
                matched_cat = k
                break
        title_list = titles[matched_cat]
        new_name = title_list[h % len(title_list)]
        price = 800.0 + (raw_price % 7700.0)

    # Enforce category-based realistic price ranges strictly
    PRICE_RANGES = {
        "smartphone": (10000, 150000),
        "laptop": (30000, 300000),
        "monitor": (8000, 100000),
        "vacuum cleaner": (5000, 40000),
        "tv": (10000, 500000),
        "headphones": (1000, 50000),
        "refrigerator": (15000, 200000)
    }

    name_lower_final = new_name.lower()
    for key, (r_min, r_max) in PRICE_RANGES.items():
        if key in name_lower_final:
            price = max(r_min, min(price, r_max))
            break

    # Let's ensure prices end realistically
    price = float(round(price))
    if price > 1000:
        remainder = price % 1000
        if remainder < 500:
            price = price - remainder + 499.0
        else:
            price = price - remainder + 900.0
    else:
        remainder = price % 100
        if remainder < 50:
            price = price - remainder + 49.0
        else:
            price = price - remainder + 99.0

    return {
        "name": new_name,
        "price": price
    }


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

                # Apply premium realistic transformation
                transformed = transform_product(ext_id, name, category, selling_price)
                name = transformed["name"]
                selling_price = transformed["price"]

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
