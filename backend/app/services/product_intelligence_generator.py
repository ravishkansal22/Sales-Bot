"""Dynamic Product Intelligence and Specification Generation Engine.

Contains template-based generators for specifications and B2B sales metadata
tailored to categories, brand tiers, pricing segments, and popularity metrics.
Absolutely no hardcoded product names, examples, or product IDs.
"""

from __future__ import annotations

import logging
import hashlib
import json
from typing import Any
from app.models.product import Product

logger = logging.getLogger(__name__)

# Category-specific ranges and thresholds
CATEGORY_PRICE_THRESHOLDS = {
    "electronics": {"budget": 10000.0, "premium": 50000.0},
    "home appliances": {"budget": 15000.0, "premium": 60000.0},
    "apparel": {"budget": 2500.0, "premium": 7500.0},
    "footwear": {"budget": 3500.0, "premium": 9000.0},
    "books": {"budget": 800.0, "premium": 2500.0},
}

PREMIUM_BRANDS = {
    "apple", "sony", "dyson", "thinkpad", "macbook", "patagonia", "bose", 
    "sennheiser", "miele", "samsung", "lg", "christian louboutin", 
    "timberland", "nike", "adidas", "dell ultrasharp", "proart", "bravia"
}

BUDGET_BRANDS = {
    "boat", "redmi", "xiaomi", "oneplus", "eureka", "kent", "haier", 
    "godrej", "acer", "jbl", "lenovo"
}

def get_product_brand_and_tier(name: str, price: float, category_key: str) -> tuple[str, str]:
    """Helper to extract brand and resolve brand positioning tier dynamically."""
    name_lower = name.lower()
    words = name_lower.split()
    brand = words[0] if words else "generic"
    
    # Try multi-word brand match (e.g. "Nike Air Max")
    for pb in PREMIUM_BRANDS:
        if pb in name_lower:
            return pb.title(), "premium"
            
    for bb in BUDGET_BRANDS:
        if bb in name_lower:
            return bb.title(), "budget"
            
    # Check if brand prefix is known
    if brand in PREMIUM_BRANDS:
        return brand.title(), "premium"
    elif brand in BUDGET_BRANDS:
        return brand.title(), "budget"
        
    # Fallback to price segment
    thresholds = CATEGORY_PRICE_THRESHOLDS.get(category_key, {"budget": 3000.0, "premium": 15000.0})
    if price <= thresholds["budget"]:
        return brand.title(), "budget"
    elif price >= thresholds["premium"]:
        return brand.title(), "premium"
    return brand.title(), "mid-range"

def generate_specs_for_product(product: Product) -> dict[str, str]:
    """Generate rich, dynamic key-value specifications and sales intelligence.

    Categorized by Electronics, Apparel, Footwear, Books, and Home Appliances.
    Attributes vary according to pricing, brand tier, and popularity.
    """
    category_raw = product.category or "General"
    category_key = category_raw.lower().strip()
    
    # Resolve Price Segment
    price = product.selling_price
    thresholds = CATEGORY_PRICE_THRESHOLDS.get(category_key, {"budget": 3000.0, "premium": 15000.0})
    
    if price <= thresholds["budget"]:
        price_segment = "budget"
    elif price >= thresholds["premium"]:
        price_segment = "premium"
    else:
        price_segment = "mid-range"
        
    # Resolve Brand Tier
    brand_name, brand_tier = get_product_brand_and_tier(product.name, price, category_key)
    
    # Combine positioning for specification variations
    is_premium = (price_segment == "premium" or brand_tier == "premium")
    is_budget = (price_segment == "budget" or brand_tier == "budget")
    
    # Use deterministic hash of product ID/Name to make values realistic but reproducible
    seed_str = f"{product.id or product.name}"
    h = int(hashlib.md5(seed_str.encode('utf-8')).hexdigest(), 16)
    
    # Initialize dynamic specifications dictionary
    specs: dict[str, str] = {}
    
    # -------------------------------------------------------------------------
    # 1. Category Specifications
    # -------------------------------------------------------------------------
    if "electronics" in category_key:
        # Connectivity
        if is_premium:
            specs["connectivity"] = "Thunderbolt 4, Wi-Fi 6E (802.11ax), Bluetooth 5.3 LE, HDMI 2.1"
            specs["battery_life"] = "Up to 24 hours of intensive B2B operations with Fast Charge support"
            specs["included_accessories"] = "Premium braided USB-C cable, travel storage pouch, 65W GaN fast charger"
            specs["material"] = "Aerospace-grade Anodized Aluminum chassis with recycled composite internals"
            specs["portability"] = "Ultra-slim ergonomic build, weighs 1.1 kg, fits in standard B2B carrying cases"
        elif is_budget:
            specs["connectivity"] = "Standard USB 2.0, Wi-Fi 4, Bluetooth 4.2"
            specs["battery_life"] = "Up to 6-8 hours of standard operating use"
            specs["included_accessories"] = "Standard USB charging cable, user setup booklet"
            specs["material"] = "High-impact textured ABS polycarbonate casing"
            specs["portability"] = "Standard dimensions, weighs 2.4 kg, robust build"
        else:
            specs["connectivity"] = "USB-C 3.2, Wi-Fi 5 (802.11ac), Bluetooth 5.0, HDMI 2.0"
            specs["battery_life"] = "Up to 12-15 hours of continuous operation"
            specs["included_accessories"] = "USB-C cable, standard charging adapter"
            specs["material"] = "Reinforced structural polymer and aluminum alloy blend"
            specs["portability"] = "Sleek travel-friendly design, weighs 1.6 kg"
            
        specs["compatibility"] = "Plug-and-play compatible with Windows 10/11, macOS, Linux, and standard B2B networks"
        specs["installation_requirements"] = "Zero configuration required; pre-calibrated firmware out of the box"
        
    elif "apparel" in category_key:
        # Material
        materials = ["Organic Cotton", "Merino Wool", "Recycled Polyester", "Nylon Blend", "Supima Cotton"]
        specs["material"] = f"{materials[h % len(materials)]} (Premium double-weave thread)" if is_premium else f"Cotton-Polyester blend (60/40)"
        
        specs["available_sizes"] = "XS, S, M, L, XL, XXL, XXXL (Standard B2B Bulk Inventory)"
        specs["available_colors"] = "Navy Blue, Carbon Black, Slate Grey, Forest Green, Classic White"
        specs["care_instructions"] = "Machine wash cold inside-out, tumble dry low, do not iron decorative highlights"
        
        if is_premium:
            specs["weather_suitability"] = "Water-repellent, windproof, thermal lining suitable for weather down to -5°C"
            specs["fit_type"] = "Tailored Athletic Fit with ergonomic joint articulation"
        elif is_budget:
            specs["weather_suitability"] = "Comfortable light insulation suitable for mild indoor/outdoor conditions"
            specs["fit_type"] = "Relaxed Comfort Fit"
        else:
            specs["weather_suitability"] = "All-season breathable layer, quick-dry technology"
            specs["fit_type"] = "Standard Regular Fit"
            
    elif "footwear" in category_key:
        specs["material"] = "Full-grain Italian Leather with waterproof treatment" if is_premium else "Synthetic leather and breathable nylon mesh"
        
        soles = ["Vibram Megagrip rubber sole with deep lugs", "EVA high-traction slip-resistant sole", "Vulcanized reinforced natural rubber"]
        specs["sole_type"] = soles[h % len(soles)] if is_premium else "Standard vulcanized carbon rubber sole"
        
        if is_premium:
            specs["comfort_level"] = "Memory foam orthotic insoles, shock-absorbing dual-density midsole, heel stabilization cup"
            specs["activity_suitability"] = "High-intensity technical training, long-shift professional wear, tactical use"
        else:
            specs["comfort_level"] = "Cushioned foam sockliner, lightweight flexible midsole"
            specs["activity_suitability"] = "All-day casual walking, everyday professional office wear"
            
        specs["sizes_available"] = "US Men 6-14, US Women 5-11 (Wide and Extra Wide options available)"

    elif "books" in category_key:
        specs["edition"] = "B2B Professional Library Edition (Hardcover Premium)" if is_premium else "Trade Paperback Edition"
        specs["language"] = "English (Available in French, German, and Spanish translation licensing)"
        
        pages = [240, 360, 480, 560, 680]
        specs["page_count"] = f"{pages[h % len(pages)]} pages"
        specs["format"] = "Smyth-sewn cloth binding with protective dust jacket" if is_premium else "Perfect-bound softcover layout"
        
        if is_premium:
            specs["audience_level"] = "Advanced executive reading, research reference, postgraduate levels"
            specs["recommended_use_cases"] = "Corporate libraries, senior leadership training programs, reference libraries"
        else:
            specs["audience_level"] = "General readership, introductory B2B curriculum, onboarding support"
            specs["recommended_use_cases"] = "Employee onboarding kits, general professional development workshops"

    elif "appliances" in category_key or "home appliances" in category_key:
        if is_premium:
            specs["energy_efficiency"] = "Energy Star Certified (A+++ Rating), eco-mode enabled"
            specs["power_consumption"] = f"{100 + (h % 3) * 50}W ultra-low operation, 0.5W standby draw"
            specs["warranty"] = "3 Years parts and labor, 10 Years motor/compressor coverage"
            specs["installation_requirements"] = "Standard 15A wall socket, professional leveling feet included"
            specs["maintenance_frequency"] = "Self-cleaning cycle; filters require replacement every 12 months"
        elif is_budget:
            specs["energy_efficiency"] = "Standard efficiency rating (A+ Rating)"
            specs["power_consumption"] = f"{350 + (h % 3) * 100}W normal load"
            specs["warranty"] = "1 Year limited manufacturer warranty"
            specs["installation_requirements"] = "Standard 3-pin residential outlet"
            specs["maintenance_frequency"] = "Manual filter rinse/vacuum required every 3 months"
        else:
            specs["energy_efficiency"] = "Energy Star Certified (A++ Rating)"
            specs["power_consumption"] = f"{200 + (h % 3) * 50}W average consumption"
            specs["warranty"] = "2 Years comprehensive manufacturer warranty"
            specs["installation_requirements"] = "Standard residential 3-pin plug socket"
            specs["maintenance_frequency"] = "Manual filter cleaning recommended every 6 months"

        specs["dimensions"] = f"{60 + (h % 3) * 5} x {55 + (h % 3) * 5} x {85 + (h % 5) * 10} cm"

    else:
        # General backup specs if category doesn't match
        specs["material"] = "Premium durable composites" if is_premium else "Standard grade polymers"
        specs["warranty"] = "2 Years comprehensive" if is_premium else "1 Year manufacturer support"
        specs["compatibility"] = "Standard industrial/commercial compatibility interfaces"
        specs["included_accessories"] = "Standard assembly and operation kit"
        
    # -------------------------------------------------------------------------
    # 2. General Specifications (Universal across all segments)
    # -------------------------------------------------------------------------
    if "warranty" not in specs:
        if is_premium:
            specs["warranty"] = "3 Years B2B Warranty with advance exchange coverage"
        elif is_budget:
            specs["warranty"] = "1 Year limited carry-in warranty"
        else:
            specs["warranty"] = "2 Years manufacturer warranty with dedicated email support"

    # -------------------------------------------------------------------------
    # 3. Create Dedicated Sales Intelligence Metadata Layer
    # -------------------------------------------------------------------------
    # The sales metadata is kept in a separate structured dictionary.
    # We will serialize this dictionary to JSON and store it under a special hidden
    # database row _sales_metadata_ in the product_specifications table.
    
    # Build segments
    customers = {
        "electronics": "Enterprise procurement managers, corporate IT deployment teams, commercial media networks, educational labs",
        "apparel": "Retail buyers, promotional event groups, hospitality client services, uniform suppliers",
        "footwear": "Industrial operations teams, athletic retail distributors, safety procurement, athletic organizations",
        "books": "Academic training institutions, B2B leadership academies, professional training developers, corporate libraries",
        "home appliances": "Commercial developers, residential building outfitters, office facility managers, hospitality managers",
    }
    ideal_customer = customers.get(category_key, "B2B procurement teams, institutional buyers, wholesale distributors")
    
    # Use cases
    cases = {
        "electronics": ["Corporate office workstations", "Enterprise hardware upgrades", "Technical research facilities", "Remote workforce setups"],
        "apparel": ["Corporate merchandise branding", "Staff uniforms and service outfits", "Promotional marketing programs", "Client gift initiatives"],
        "footwear": ["All-day shift labor environments", "Outdoor field operations", "Industrial facility tours", "Athletic training and recreation"],
        "books": ["Professional development programs", "Onboarding resource materials", "B2B skill training workshops", "Executive education libraries"],
        "home appliances": ["Office breakroom installations", "Commercial property fittings", "Hospitality suite upgrades", "Residential building construction"],
    }
    use_cases = cases.get(category_key, ["Commercial deployments", "B2B supply programs", "Institutional use"])
    
    # Key advantages
    advs = {
        "electronics": ["Reliable operational uptime", "Seamless enterprise network integration", "Superior energy efficiency and thermal ratings", "Advanced hardware-level security compliance"],
        "apparel": ["High fabric durability under frequent laundry cycles", "Consistent B2B batch dye color consistency", "Breathable, wear-resistant organic fabric fibers", "Generous size scaling curves"],
        "footwear": ["Premium slip-resistant traction", "Orthotic support for long-hour shifts", "Tear-resistant double-reinforced stitching", "Lightweight material compositions"],
        "books": ["Peer-reviewed technical accuracy", "High-durability binding materials", "Structured, digestible diagrams and summaries", "Industry-recognized thought-leadership authors"],
        "home appliances": ["Optimized energy ratings reducing utility bills", "Commercial-grade motor and compressor endurance", "Quiet operation decibel range", "Low maintenance requirements"],
    }
    key_advantages = advs.get(category_key, ["High reliability under heavy workloads", "Excellent total cost of ownership", "Easy drop-in deployment", "Dedicated warranty backing"])
    
    # Objection Handling responses (Pricing, Warranty, Maintenance, Compatibility, Longevity)
    objection_price = ""
    objection_warranty = ""
    objection_maintenance = ""
    objection_compatibility = ""
    objection_longevity = ""
    
    if is_premium:
        objection_price = f"While the upfront procurement cost of the {product.name} is higher, the premium build materials and lower energy/maintenance profiles result in a significantly lower total cost of ownership (TCO) over its life cycle."
        objection_warranty = "We back this model with an industry-leading 3-year warranty that includes advanced exchange routing, meaning any issues are resolved within 24 hours to eliminate downtime."
        objection_maintenance = "Engineered with self-calibrating components requiring virtually zero active maintenance, letting your team focus entirely on operational tasks."
        objection_compatibility = "Fully compatible with standard industrial formats, including drop-in interfaces for easy integration with your existing fleet or setup."
        objection_longevity = "Constructed with premium component bases rated for over 50,000 hours of continuous operations under heavy commercial workloads."
    elif is_budget:
        objection_price = f"The {product.name} offers standard features at a highly competitive budget threshold, allowing your organization to scale deployment without stretching initial budget boundaries."
        objection_warranty = "Includes a solid 1-year manufacturer warranty that covers all essential operating parts, with extensions available for B2B contracts."
        objection_maintenance = "Designed for simple, manual maintenance procedures that can be executed quickly by your team without needing expensive third-party service calls."
        objection_compatibility = "Utilizes universal plug-and-play interfaces to ensure immediate compatibility out of the box with standard setups."
        objection_longevity = "Built to standard commercial durability specifications, offering a solid operational lifespan for all typical business requirements."
    else:
        objection_price = f"This model balances commercial durability and price, offering an excellent price-to-performance ratio that optimizes B2B purchase value."
        objection_warranty = "Supported by our standard 2-year manufacturer warranty, with responsive ticket support and complete parts replacement."
        objection_maintenance = "Standard cleaning/inspection cycles are scheduled once every 6 months to guarantee maximum performance lifespan."
        objection_compatibility = "Constructed to match all standard industry interfaces for hassle-free compatibility."
        objection_longevity = "Built with reinforced polymers and solid-state parts, rated for years of trouble-free daily commercial usage."

    # Dynamic Complementary recommendations (accessories, extended warranty, plans)
    recommendations = []
    if "electronics" in category_key:
        recommendations = [
            {"name": "B2B Pro Support Plus", "type": "warranty", "desc": "Extend warranty to 5 years with direct engineer support"},
            {"name": "Braided Heavy-Duty Cable Pack", "type": "accessory", "desc": "Reinforced connections for high-wear workstations"},
            {"name": "Universal Docking Station", "type": "deployment add-on", "desc": "Expand standard connectivity ports"},
        ]
    elif "apparel" in category_key or "footwear" in category_key:
        recommendations = [
            {"name": "Heavy-Duty Laundry Garment Bags", "type": "maintenance", "desc": "Protects stitching and fabric during wash cycles"},
            {"name": "Waterproof Protector Spray Pack", "type": "care", "desc": "Repels dirt and moisture to double product lifetime"},
        ]
    elif "books" in category_key:
        recommendations = [
            {"name": "Digital Companion License", "type": "digital upgrade", "desc": "Access interactive code labs and online updates"},
            {"name": "Bulk Distribution Display Rack", "type": "accessory", "desc": "Organize B2B reference materials on floor layouts"},
        ]
    else:
        recommendations = [
            {"name": "Commercial Annual Maintenance Plan", "type": "maintenance plan", "desc": "Scheduled inspections and performance reports"},
            {"name": "Deluxe Replacement Parts Kit", "type": "accessories", "desc": "Includes gaskets, filters, and standard accessories"},
        ]

    # Assemble sales intelligence metadata structure
    sales_metadata = {
        "brand_name": brand_name,
        "brand_tier": brand_tier,
        "price_segment": price_segment,
        "ideal_customer": ideal_customer,
        "use_cases": use_cases,
        "key_advantages": key_advantages,
        "objection_handling": {
            "price": objection_price,
            "warranty": objection_warranty,
            "maintenance": objection_maintenance,
            "compatibility": objection_compatibility,
            "longevity": objection_longevity
        },
        "cross_sell_recommendations": recommendations
    }
    
    # Store sales metadata serialized as JSON under a special key
    specs["_sales_metadata_"] = json.dumps(sales_metadata)
    
    return specs
