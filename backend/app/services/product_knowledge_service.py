from __future__ import annotations

import logging
import uuid
import re
import asyncio
import json
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.product_specification import ProductSpecification
from app.services.llm.base import LLMProvider
from app.services.product_resolver import ProductResolver
from app.services.product_service import ProductService
from app.core.config_layer import NegotiationConfig

logger = logging.getLogger(__name__)



def extract_attribute_by_regex(question: str, documents: list[str], threshold: float = 0.75) -> tuple[str | None, float]:
    question_lower = question.lower()
    
    # 1. Extract non-stopword keywords from question
    stopwords = {
        "what", "is", "the", "of", "for", "product", "a", "an", "does", "have", "how",
        "about", "any", "are", "by", "in", "on", "with", "to", "from", "at", "it", "its",
        "which", "can", "you", "tell", "me", "show", "give", "info", "information",
        "spec", "specs", "specification", "specifications", "please", "detail", "details"
    }
    words = re.findall(r"\b\w{3,20}\b", question_lower)
    raw_keywords = [w for w in words if w not in stopwords]
    
    if not raw_keywords:
        return None, 0.0

    # Expand keywords using synonyms
    synonyms_map = {
        "heavy": ["weight", "weighs", "heavy"],
        "weighs": ["weight", "heavy", "weighs"],
        "weight": ["weight", "heavy", "weighs"],
        "color": ["color", "colour"],
        "colour": ["color", "colour"],
        "size": ["size", "dimension", "dimensions", "width", "height", "length", "depth"],
        "dimension": ["size", "dimension", "dimensions", "width", "height", "length", "depth"],
        "dimensions": ["size", "dimension", "dimensions", "width", "height", "length", "depth"],
        "warranty": ["warranty", "guarantee"],
        "guarantee": ["warranty", "guarantee"],
        "capacity": ["capacity", "volume", "battery", "storage"],
        "ports": ["port", "ports", "usb", "hdmi", "connection", "connections"],
        "material": ["material", "made", "constructed", "composition"],
    }
    
    keywords = []
    for rk in raw_keywords:
        if rk in synonyms_map:
            keywords.extend(synonyms_map[rk])
        else:
            keywords.append(rk)
    keywords = list(set(keywords))  # Deduplicate

    # Combine documents into one text
    full_text = "\n".join(documents)
    full_text_lower = full_text.lower()
    
    best_match = None
    best_confidence = 0.0
    
    units_pattern = r"(?:kg|g|lbs|oz|mah|wh|w|v|ah|gb|tb|mb|hours|hrs|years|yrs|months|mths|ports|usb|hdmi|cm|mm|inches|inch|in|ft|m|l|ml|liters|litres|v)"
    dim_regex = r"\b(\d+(?:\.\d+)?\s*(?:cm|mm|inches|inch|in|m|ft)?\s*(?:x|by)\s*\d+(?:\.\d+)?\s*(?:cm|mm|inches|inch|in|m|ft)?\s*(?:(?:x|by)\s*\d+(?:\.\d+)?\s*(?:cm|mm|inches|inch|in|m|ft)?)?)\b"

    # Categorize keyword sets
    color_keys = {"color", "colour"}
    material_keys = {"material", "made", "constructed", "composition"}
    dimension_keys = {"size", "dimension", "dimensions", "width", "height", "length", "depth"}

    for kw in keywords:
        kw_pattern = rf"\b{re.escape(kw)}\b"
        for kw_match in re.finditer(kw_pattern, full_text_lower):
            kw_start = kw_match.start()
            
            # --- 1. Scan window after keyword (60 chars) ---
            window_after = full_text[kw_start:kw_start + 60]
            
            # A. Key-Value style: kw: value (applies to all)
            kv_regex = rf"\b{re.escape(kw)}\s*[:\-–=]\s*([^.\n,;()]+)"
            kv_match = re.search(kv_regex, window_after, re.IGNORECASE)
            if kv_match:
                val = kv_match.group(1).strip()
                if val and len(val) < 40:
                    if not re.search(r"\b(is|and|the|a|for|with)\b", val.lower()):
                        confidence = 0.9
                        if confidence > best_confidence:
                            best_match = val
                            best_confidence = confidence

            # B. Dimension pattern (only for dimension keys)
            if kw in dimension_keys:
                dim_match = re.search(dim_regex, window_after, re.IGNORECASE)
                if dim_match:
                    val = dim_match.group(1).strip()
                    confidence = 0.9
                    if confidence > best_confidence:
                        best_match = val
                        best_confidence = confidence

            # C. Number + Unit pattern (only for measurement/unit keys)
            if kw not in color_keys and kw not in material_keys and kw not in dimension_keys:
                unit_match = re.search(rf"\b(\d+(?:\.\d+)?\s*{units_pattern}\b)", window_after, re.IGNORECASE)
                if unit_match:
                    val = unit_match.group(1).strip()
                    confidence = 0.85
                    if confidence > best_confidence:
                        best_match = val
                        best_confidence = confidence            # D. Adjective/Descriptive words after keyword (only for color/material keys)
            if kw in color_keys or kw in material_keys:
                desc_post_regex = rf"\b{re.escape(kw)}\s+(?:is|of|with|has)?\s*([a-zA-Z]{{3,15}}(?:\s+[a-zA-Z]{{3,15}})?)\b"
                desc_post_match = re.search(desc_post_regex, window_after, re.IGNORECASE)
                if desc_post_match:
                    val = desc_post_match.group(1).strip()
                    first_word = val.split()[0].lower() if val else ""
                    forbidden_start = {"and", "or", "but", "the", "a", "an", "with", "is", "of", "in", "at", "by", "for", "to", "has", "have", "weighs", "weigh", "weighing"}
                    if first_word and first_word not in forbidden_start:
                        confidence = 0.85
                        if confidence > best_confidence:
                            best_match = val
                            best_confidence = confidence

            # --- 2. Scan window before keyword (60 chars) ---
            window_start = max(0, kw_start - 60)
            window_before = full_text[window_start:kw_start + len(kw)]
            
            # A. Number + Unit before keyword (only for measurement/unit keys)
            if kw not in color_keys and kw not in material_keys and kw not in dimension_keys:
                pre_regex = rf"\b(\d+(?:\.\d+)?\s*(?:-?\w+)?)\s+{re.escape(kw)}\b"
                pre_match = re.search(pre_regex, window_before, re.IGNORECASE)
                if pre_match:
                    val = pre_match.group(1).strip()
                    confidence = 0.85
                    if confidence > best_confidence:
                        best_match = f"{val} {kw}"
                        best_confidence = confidence

            # B. Adjective/Descriptive words before keyword (only for color/material keys)
            if kw in color_keys or kw in material_keys:
                desc_pre_regex = rf"\b([a-zA-Z]{{3,15}}(?:\s+[a-zA-Z]{{3,15}})?)\s+{re.escape(kw)}\b"
                desc_pre_match = re.search(desc_pre_regex, window_before, re.IGNORECASE)
                if desc_pre_match:
                    val = desc_pre_match.group(1).strip()
                    first_word = val.split()[0].lower() if val else ""
                    forbidden_start = {"and", "or", "but", "the", "a", "an", "with", "is", "of", "in", "at", "by", "for", "to", "has", "have", "comes", "available", "weighs", "weigh", "weighing"}
                    if first_word and first_word not in forbidden_start:
                        confidence = 0.85
                        if confidence > best_confidence:
                            best_match = val
                            best_confidence = confidence

    if best_confidence >= threshold and best_match:
        return best_match.strip(" -:="), best_confidence
        
    return None, 0.0


CANONICAL_SYNONYMS = {
    "color": ["color", "colour", "shade", "hue"],
    "warranty": ["warranty", "guarantee", "warranty period"],
    "processor": ["processor", "cpu", "chip", "chipset", "soc"],
    "memory": ["memory", "ram", "storage", "capacity"],
    "battery": ["battery", "mah", "battery capacity", "battery life"],
    "camera": ["camera", "megapixels", "mp", "resolution", "lens"],
    "dimensions": ["dimensions", "size", "height", "width", "depth", "length", "dimension"],
    "display": ["display", "screen", "panel"],
}

GENERIC_CATEGORY_STANDARDS = {
    "electronics": {
        "warranty": "Consumer electronics typically feature a standard 1-year or 2-year manufacturer warranty covering parts and labor.",
        "color": "Electronic devices are commonly manufactured in standard colors like black, white, silver, grey, or space gray.",
        "dimensions": "Electronics and gadgets vary widely in dimensions based on the specific type (e.g. phones, laptops, audio equipment), but standard sizes are designed for portability or standard desk setups.",
        "battery": "Portable electronic products typically contain lithium-ion rechargeable batteries with capacity designed for 1 to 2 days of normal usage.",
        "processor": "Modern consumer electronics use integrated microprocessors or chipsets suited for their application class.",
        "memory": "Electronic storage device capacity varies from gigabytes (GB) for RAM/cache to terabytes (TB) for internal storage drives.",
        "camera": "Smart devices and electronics with cameras generally include lenses ranging from 8MP to 108MP depending on device tier.",
    },
    "home appliances": {
        "warranty": "Major and small home appliances typically carry a standard 1 to 5 years manufacturer warranty, often with extended coverage for key components like motors or compressors.",
        "color": "Home appliances are usually finished in classic neutral colors such as white, black, stainless steel, or chrome.",
        "dimensions": "Home appliances have standard utility dimensions designed to fit common kitchen counters, cabinets, or laundry spaces.",
        "power": "Appliances are designed to run on standard residential AC voltages (110V/220V).",
    },
    "apparel": {
        "warranty": "Apparel items generally do not carry extended warranties, but usually offer a limited return or exchange window (e.g., 30 days) for manufacturing defects.",
        "color": "Apparel products are produced in a vast array of seasonal colors, shades, patterns, and fabrics.",
        "dimensions": "Clothing sizes follow standard sizing charts (e.g., S, M, L, XL, or chest/waist measurements) varying by region and fit style.",
        "material": "Apparel is typically made from cotton, polyester, wool, linen, or standard synthetic blends.",
    },
    "footwear": {
        "warranty": "Footwear generally doesn't have a long-term warranty but usually includes a return window for manufacturing defects.",
        "color": "Footwear is available in many colorways including black, white, brown, grey, and athletic color accents.",
        "dimensions": "Footwear sizes follow standard scale numbers (US, UK, EU sizing) for men, women, or kids.",
        "material": "Footwear is commonly made of leather, synthetic mesh, rubber, canvas, or specialized cushioning foams.",
    },
    "books": {
        "warranty": "Books are physical print products and do not have manufacturer warranties, though they are subject to standard return policies for printing defects.",
        "color": "Books have cover artwork of various colors, and paper text pages that are typically off-white, cream, or white.",
        "dimensions": "Books are printed in standard trim sizes such as paperback (mass market), trade paperback, or hardcover sizes.",
        "material": "Books are made of paper, cardboard, binding glue, and print ink.",
    }
}


class ProductAnswer(BaseModel):
    """Structured container for product Q&A answers and internal telemetry."""
    customer_response: str = Field(..., description="Clean, customer-facing response text")
    source: str = Field(..., description="Information source: catalog, web, general_knowledge, or none")
    confidence: float = Field(..., description="Confidence score of the answer")
    internal_notes: str = Field(..., description="Internal explanation or reasoning")
    resolved_attribute: str | None = Field(default=None, description="The canonical attribute resolved")
    resolved_value: str | None = Field(default=None, description="The extracted/resolved value of the attribute")


SAFE_GENERIC_ATTRIBUTES = {
    "color", "processor", "chipset", "battery", "memory", "storage", "camera", "display"
}
STRICT_PRODUCT_SPECIFIC_ATTRIBUTES = {
    "pages", "isbn", "dimensions", "weight", "release date", "model number", "serial number"
}
HIGH_PRIORITY_ATTRIBUTES = {
    "processor", "chipset", "cpu", "ram", "memory", "storage", "battery", "display", "color", "camera", "warranty", "support", "connectivity", "bluetooth", "wireless"
}


def normalize_attribute(q_lower: str) -> str | None:
    # Multi-word synonyms first
    if "warranty period" in q_lower:
        return "warranty"
    if "battery capacity" in q_lower or "battery life" in q_lower:
        return "battery"
    if "release date" in q_lower or "launch date" in q_lower or "publication date" in q_lower:
        return "release date"
    if "model number" in q_lower or "model no" in q_lower:
        return "model number"
    if "serial number" in q_lower or "serial no" in q_lower:
        return "serial number"
    if "page count" in q_lower or "number of pages" in q_lower:
        return "pages"

    words = set(re.findall(r"\b\w+\b", q_lower))
    mappings = {
        "color": ["colour", "shade", "hue", "color"],
        "warranty": ["guarantee", "warranty"],
        "processor": ["cpu", "chip", "chipset", "processor", "soc"],
        "memory": ["ram", "storage", "capacity", "memory"],
        "battery": ["mah", "battery"],
        "camera": ["megapixels", "mp", "resolution", "lens", "camera"],
        "dimensions": ["size", "height", "width", "depth", "length", "dimension", "dimensions"],
        "pages": ["page", "pages"],
        "isbn": ["isbn", "isbn10", "isbn13"],
        "weight": ["weight", "weighs", "heavy", "heaviness", "mass"],
        "display": ["display", "screen", "panel"],
        "support": ["support", "service", "help", "assistance"],
        "connectivity": ["connectivity", "ports", "connections", "usb", "hdmi"],
        "bluetooth": ["bluetooth", "bt"],
        "wireless": ["wireless", "wifi", "wi-fi"],
    }
    for canonical, synonyms in mappings.items():
        for syn in synonyms:
            if syn in words:
                return canonical
    return None


def get_category_standard(category: str | None, canonical_attr: str) -> str:
    if not category:
        return ""
    cat_lower = category.lower()
    matched_cat = None
    for k in GENERIC_CATEGORY_STANDARDS:
        if k in cat_lower or cat_lower in k:
            matched_cat = k
            break
    if matched_cat and canonical_attr in GENERIC_CATEGORY_STANDARDS[matched_cat]:
        return GENERIC_CATEGORY_STANDARDS[matched_cat][canonical_attr]
    return ""


class GeneralKnowledgeEstimate(BaseModel):
    """Pydantic model for general knowledge estimate LLM output."""
    answer: str = Field(..., description="Estimated specification value or explanation")
    confidence: float = Field(..., description="Confidence score between 0.0 and 1.0")
    reasoning: str = Field(..., description="Reasoning for this estimate")

class ProductKnowledgeService:
    """Service to route user intents and answer product questions/comparisons using catalog-backed data."""

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    async def answer_product_question(
        self,
        product: Product,
        question: str,
        db: AsyncSession,
    ) -> ProductAnswer:
        """Answer a product question dynamically using catalog fields and database specifications.

        Ensures separation of Catalog-Backed Facts and General Knowledge estimates.
        """
        # Structured Diagnostics for specification retrieval
        q_lower = question.lower()
        canonical_attr = normalize_attribute(q_lower)
        logger.info(
            "[DIAGNOSTICS - SPECIFICATION RETRIEVAL] Query: '%s', Resolved Attribute: '%s', Product ID: %s",
            question, canonical_attr, product.id
        )

        # 2. Catalog Lookup (Database)
        stmt = select(ProductSpecification).where(ProductSpecification.product_id == product.id)
        result = await db.execute(stmt)
        specs = result.scalars().all()

        # Lazy Self-Healing Generation:
        # (a) If no specifications exist for this product, generate them dynamically.
        # (b) If electronics metadata is stale (missing 'subcategory' key, i.e. generated
        #     before subcategory-aware logic existed), delete and regenerate to fix language.
        from app.services.product_intelligence_generator import generate_specs_for_product

        needs_regeneration = False
        if not specs:
            needs_regeneration = True
            logger.info(
                "[DIAGNOSTICS - SPECIFICATION RETRIEVAL] Self-healing initiated (no specs): "
                "Product %s (%s)", product.name, str(product.id)
            )
        elif product.category and "electronics" in product.category.lower():
            # Check for stale metadata lacking subcategory field
            for s in specs:
                if s.specification_name.lower().strip() == "_sales_metadata_":
                    try:
                        existing_meta = json.loads(s.specification_value)
                        if "subcategory" not in existing_meta:
                            needs_regeneration = True
                            logger.info(
                                "[DIAGNOSTICS - SPECIFICATION RETRIEVAL] Stale metadata detected "
                                "(no subcategory field): regenerating specs for Product %s",
                                product.name
                            )
                    except Exception:
                        needs_regeneration = True
                    break

        if needs_regeneration:
            if specs:  # delete stale specs before regenerating
                for old_spec in specs:
                    await db.delete(old_spec)
                await db.flush()
            generated_specs = generate_specs_for_product(product)
            specs_to_add = []
            for s_name, s_val in generated_specs.items():
                spec_obj = ProductSpecification(
                    id=uuid.uuid4(),
                    product_id=product.id,
                    specification_name=s_name,
                    specification_value=s_val
                )
                db.add(spec_obj)
                specs_to_add.append(spec_obj)
            await db.commit()
            specs = specs_to_add

        # Build user-facing spec_dict — exclude ALL underscore-prefixed internal fields.
        # _sales_metadata_ is parsed separately; any other _-prefixed key is also suppressed.
        spec_dict = {}
        sales_metadata = {}
        for s in specs:
            name_lower = s.specification_name.lower().strip()
            if name_lower.startswith("_"):
                # Internal field — parse sales metadata if applicable, then skip
                if name_lower == "_sales_metadata_":
                    try:
                        sales_metadata = json.loads(s.specification_value)
                    except Exception as e:
                        logger.warning("Failed to parse sales metadata JSON: %s", e)
                continue  # never add to spec_dict
            spec_dict[name_lower] = s.specification_value

        # Add only customer-relevant catalog fields; internal metrics are excluded
        spec_dict["category"] = product.category
        spec_dict["price"] = f"INR {product.selling_price:,.2f}"
        # Note: stock, popularity, and return_rate are internal metrics — not added to spec_dict

        matched_spec_name = None
        matched_spec_val = None

        if canonical_attr:
            # Check canonical attribute and its synonyms in spec_dict
            syns = CANONICAL_SYNONYMS.get(canonical_attr, [canonical_attr])
            for spec_name, spec_val in spec_dict.items():
                spec_norm = normalize_attribute(spec_name)
                if spec_norm == canonical_attr:
                    matched_spec_name = spec_name
                    matched_spec_val = spec_val
                    break
                if any(
                    syn in spec_name
                    or spec_name in syn
                    for syn in syns
                ):
                    matched_spec_name = spec_name
                    matched_spec_val = spec_val
                    break

        # Fallback to simple substring match if not found via canonical attributes
        if not matched_spec_name:
            for spec_name, val in spec_dict.items():
                if spec_name in q_lower:
                    matched_spec_name = spec_name
                    matched_spec_val = val
                    break

        # Internal catalog fields that should never be surfaced as direct spec answers.
        # These are operational/internal metrics, not customer-facing selling points.
        _INTERNAL_CATALOG_FIELDS = {"stock", "popularity", "return rate", "price", "category"}

        if matched_spec_name and matched_spec_val and matched_spec_name not in _INTERNAL_CATALOG_FIELDS:
            logger.info(
                "[DIAGNOSTICS - SPECIFICATION RETRIEVAL] Catalog Match Found. Spec Name: '%s', Value: '%s'",
                matched_spec_name, matched_spec_val
            )
            return ProductAnswer(
                customer_response=(
                    f"The {product.name} — {matched_spec_name.title()}: {matched_spec_val}.\n\n"
                    f"Anything else you'd like to know about it?"
                ),
                source="catalog",
                confidence=1.0,
                internal_notes="Catalog-backed fact retrieved from database specifications.",
                resolved_attribute=canonical_attr or matched_spec_name,
                resolved_value=matched_spec_val
            )

        # Determine strict category
        is_strict = False
        if canonical_attr in STRICT_PRODUCT_SPECIFIC_ATTRIBUTES:
            is_strict = True
        elif canonical_attr not in SAFE_GENERIC_ATTRIBUTES:
            # If it is not recognized as a safe generic attribute, treat it as strict by default
            is_strict = True

        # 3. Cache Check
        q_norm = re.sub(r"\W+", "", q_lower)
        cache_key = f"final_ans_cache:{product.id}:{q_norm}"
        
        # Check Redis if available
        from app.services.redis_service import _redis_service
        if _redis_service is not None:
            try:
                cached_ans = await _redis_service.get(cache_key)
                if cached_ans:
                    from app.services.llm_service import metrics_service
                    metrics_service.increment("cache_hits")
                    logger.info("Cache hit for key: %s", cache_key)
                    return ProductAnswer.model_validate_json(cached_ans)
            except Exception as e:
                logger.warning("Redis read failed: %s", e)
        
        # Check in-memory dict fallback
        if not hasattr(ProductKnowledgeService, "_in_memory_cache"):
            ProductKnowledgeService._in_memory_cache = {}
        cached_ans = ProductKnowledgeService._in_memory_cache.get(cache_key)
        if cached_ans:
            from app.services.llm_service import metrics_service
            metrics_service.increment("cache_hits")
            logger.info("Cache hit (in-memory) for key: %s", cache_key)
            if isinstance(cached_ans, str):
                return ProductAnswer.model_validate_json(cached_ans)
            elif isinstance(cached_ans, dict):
                return ProductAnswer.model_validate(cached_ans)
            return cached_ans
            
        from app.services.llm_service import metrics_service
        metrics_service.increment("cache_misses")

        # Cache helper function
        async def save_to_cache(key: str, val: ProductAnswer):
            val_json = val.model_dump_json()
            if _redis_service is not None:
                try:
                    await _redis_service.set(key, val_json, ttl=86400)
                except Exception as e:
                    logger.warning("Redis write failed: %s", e)
            ProductKnowledgeService._in_memory_cache[key] = val

        # 4. Web Retrieval (Category-Aware query generation)
        category_lower = product.category.lower() if product.category else ""
        name_lower = product.name.lower()
        
        if canonical_attr == "color":
            if "book" in category_lower:
                search_query = f"{product.name} cover color book cover"
            elif "phone" in category_lower or "mobile" in category_lower or "phone" in name_lower or "iphone" in name_lower:
                search_query = f"{product.name} colors available colors"
            elif "laptop" in category_lower or "computer" in category_lower or "laptop" in name_lower or "macbook" in name_lower:
                search_query = f"{product.name} color options"
            else:
                search_query = f"{product.name} colors available options"
        elif canonical_attr == "pages" or ("page" in q_lower or "pages" in q_lower):
            search_query = f"{product.name} page count number of pages"
        elif canonical_attr == "isbn" or "isbn" in q_lower:
            search_query = f"{product.name} isbn specifications"
        elif canonical_attr == "dimensions" or ("size" in q_lower or "dimension" in q_lower):
            if "book" in category_lower:
                search_query = f"{product.name} book size dimensions"
            else:
                search_query = f"{product.name} dimensions specifications"
        elif canonical_attr == "weight" or ("weight" in q_lower or "weigh" in q_lower):
            search_query = f"{product.name} weight specs weight grams lbs"
        elif canonical_attr == "release date" or ("release" in q_lower or "launch" in q_lower or "publish" in q_lower):
            if "book" in category_lower:
                search_query = f"{product.name} publication release date"
            else:
                search_query = f"{product.name} release date launch date"
        elif canonical_attr == "model number" or "model" in q_lower:
            search_query = f"{product.name} model number specifications"
        elif canonical_attr == "serial number" or "serial" in q_lower:
            search_query = f"{product.name} serial number model number"
        else:
            search_query = f"{product.name} {question} specifications"

        # Safe attributes multi-query variations
        queries = []
        is_safe = canonical_attr in SAFE_GENERIC_ATTRIBUTES
        SOFT_GENERIC_ATTRIBUTES = {"color", "memory", "storage", "display", "connectivity", "bluetooth", "wireless"}
        is_soft = canonical_attr in SOFT_GENERIC_ATTRIBUTES
        is_high_priority = canonical_attr in HIGH_PRIORITY_ATTRIBUTES

        if is_high_priority:
            attr_syns = {
                "processor": ["processor", "chipset", "cpu"],
                "chipset": ["chipset", "processor", "cpu"],
                "ram": ["ram", "memory", "specs"],
                "memory": ["memory", "ram", "storage"],
                "storage": ["storage", "memory", "gb"],
                "battery": ["battery", "mah", "battery life"],
                "display": ["display", "screen", "panel"],
                "color": ["color", "colour", "options"],
                "camera": ["camera", "megapixels", "lens"],
                "warranty": ["warranty", "guarantee", "support"],
                "support": ["support", "service", "warranty"],
                "connectivity": ["connectivity", "ports", "connections"],
                "bluetooth": ["bluetooth", "wireless", "connectivity"],
                "wireless": ["wireless", "wifi", "bluetooth"]
            }
            syns = attr_syns.get(canonical_attr, [canonical_attr])
            while len(syns) < 3:
                syns.append(canonical_attr)
            
            queries = [
                f"{product.name} {syns[0]}",
                f"{product.name} {syns[1]}",
                f"{product.name} {syns[2]}",
                f"{product.name} specifications",
                f"{product.name} technical specs"
            ]
        elif is_safe:
            if canonical_attr == "color":
                queries = [
                    f"{product.name} colors available colors",
                    f"{product.name} color options",
                    f"{product.name} available colors options",
                    f"{product.name} color specs"
                ]
            elif canonical_attr == "processor":
                queries = [
                    f"{product.name} processor specs",
                    f"{product.name} cpu chip",
                    f"{product.name} processor model specs",
                    f"{product.name} cpu processor"
                ]
            elif canonical_attr == "chipset":
                queries = [
                    f"{product.name} chipset specs",
                    f"{product.name} processor chip specs",
                    f"{product.name} cpu chipset",
                    f"{product.name} motherboard chipset"
                ]
            elif canonical_attr == "camera":
                queries = [
                    f"{product.name} camera specs",
                    f"{product.name} camera megapixels",
                    f"{product.name} camera resolution",
                    f"{product.name} lens specifications"
                ]
            elif canonical_attr == "battery":
                queries = [
                    f"{product.name} battery specs",
                    f"{product.name} battery capacity mah",
                    f"{product.name} battery life hours",
                    f"{product.name} battery specification"
                ]
            elif canonical_attr in ("memory", "storage"):
                queries = [
                    f"{product.name} memory specifications",
                    f"{product.name} ram storage capacity",
                    f"{product.name} internal storage gb",
                    f"{product.name} storage options"
                ]
            else:
                queries = [
                    f"{product.name} {canonical_attr} specs",
                    f"{product.name} {question} specifications",
                    f"{product.name} {canonical_attr} options"
                ]
        else:
            queries = [search_query]

        combined_queries_str = "||".join(queries)
        ret_cache_key = f"retrieval_cache:{re.sub(r'\W+', '', combined_queries_str.lower())[:100]}"
        retrieved_docs = []
        
        from app.services.redis_service import _redis_service
        if _redis_service is not None:
            try:
                retrieved_docs = await _redis_service.get(ret_cache_key)
            except Exception as e:
                logger.warning("Redis read for retrieval cache failed: %s", e)
                
        if not retrieved_docs:
            if hasattr(ProductKnowledgeService, "_in_memory_retrieval_cache"):
                retrieved_docs = ProductKnowledgeService._in_memory_retrieval_cache.get(ret_cache_key)
                
        if not retrieved_docs:
            import asyncio
            from app.services.retrieval_provider import get_retrieval_provider
            provider = get_retrieval_provider()
            try:
                tasks = [provider.retrieve(q) for q in queries]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                logger.info(
                    "Retrieval queries: %s",
                    queries
                )

                logger.info(
                    "Retrieved docs count: %d",
                    len(retrieved_docs)
                )
                seen = set()
                for res in results:
                    if isinstance(res, list):
                        for doc in res:
                            if doc and doc not in seen:
                                seen.add(doc)
                                retrieved_docs.append(doc)
                    elif isinstance(res, Exception):
                        logger.error("Web retrieval variation query failed: %s", res)
            except Exception as e:
                logger.error("Parallel web retrieval failed: %s", e)
                retrieved_docs = []

                logger.info(
                    "Retrieved docs count: %d",
                    len(retrieved_docs)
                )

                logger.info(
                    "Retrieved queries: %s",
                    queries
                )
            
            if retrieved_docs:
                if _redis_service is not None:
                    try:
                        await _redis_service.set(ret_cache_key, retrieved_docs, ttl=86400)
                    except Exception as e:
                        logger.warning("Redis write for retrieval cache failed: %s", e)
                if not hasattr(ProductKnowledgeService, "_in_memory_retrieval_cache"):
                    ProductKnowledgeService._in_memory_retrieval_cache = {}
                ProductKnowledgeService._in_memory_retrieval_cache[ret_cache_key] = retrieved_docs

        # 5. Regex Extraction
        extracted_value = None
        confidence = 0.0

        # Define distinct thresholds based on attribute classification
        soft_attributes = {"color", "display", "memory", "storage", "connectivity", "bluetooth", "wireless"}
        commercial_attributes = {"warranty", "support"}
        technical_attributes = {"processor", "chipset", "battery", "camera"}

        if canonical_attr in soft_attributes:
            web_threshold = 0.45
            extract_threshold = 0.40
        elif canonical_attr in commercial_attributes:
            web_threshold = 0.50
            extract_threshold = 0.45
        elif canonical_attr in technical_attributes:
            web_threshold = 0.60
            extract_threshold = 0.55
        else:
            if is_soft:
                extract_threshold = 0.50
            elif is_safe:
                extract_threshold = 0.60
            else:
                extract_threshold = 0.75
            web_threshold = 0.60 if is_safe else 0.75

        if retrieved_docs:
            extracted_value, confidence = extract_attribute_by_regex(question, retrieved_docs, threshold=extract_threshold)
            
        if extracted_value:
            if confidence >= web_threshold:
                ans = ProductAnswer(
                    customer_response=(
                        f"Regarding the {product.name}, the {canonical_attr or 'requested specification'} is {extracted_value}."
                    ),
                    source="web",
                    confidence=confidence,
                    internal_notes=f"Web-retrieved information via regex extraction. Confidence: {confidence:.2f}",
                    resolved_attribute=canonical_attr,
                    resolved_value=extracted_value
                )
                await save_to_cache(cache_key, ans)
                return ans
            elif 0.50 <= confidence < web_threshold:
                if is_soft:
                    ans = ProductAnswer(
                        customer_response=(
                            f"Regarding the {product.name}, the {canonical_attr or 'requested specification'} is {extracted_value}."
                        ),
                        source="general_knowledge",
                        confidence=confidence,
                        internal_notes=(
                            f"General Knowledge Estimate based on regex web search match.\n"
                            f"Disclaimer: This is an estimate based on search results and not verified from the official product specifications catalog."
                        ),
                        resolved_attribute=canonical_attr,
                        resolved_value=extracted_value
                    )
                    await save_to_cache(cache_key, ans)
                    return ans

        # 6. LLM Web Extraction
        if retrieved_docs:
            system_prompt = (
                "You are a product specification extractor. Your task is to extract the answer to the customer's question "
                "from the provided web documents. Do NOT make up information.\n"
                "Return a JSON object conforming exactly to this schema:\n"
                "{\n"
                "  \"answer\": \"extracted specification value or detailed answer\",\n"
                "  \"confidence\": 0.9  // float between 0.0 and 1.0\n"
                "}\n"
                "If the information is not present in the documents or cannot be inferred, return confidence 0.0 and answer '[Specification Unavailable]'."
            )
            
            docs_text = "\n\n".join(f"Document {i+1}:\n{doc}" for i, doc in enumerate(retrieved_docs))
            prompt = (
                f"Product Name: {product.name}\n"
                f"Question: {question}\n\n"
                f"Web Search Results:\n{docs_text}\n\n"
                f"Extract the answer in JSON format."
            )
            
            try:
                class WebExtraction(BaseModel):
                    answer: str
                    confidence: float
                
                extracted_obj = await self._llm.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    response_model=WebExtraction
                )
                
                if "[Specification Unavailable]" not in extracted_obj.answer:
                    if extracted_obj.confidence >= web_threshold:
                        ans = ProductAnswer(
                            customer_response=(
                                f"Regarding the {product.name}, the {canonical_attr or 'requested specification'} is {extracted_obj.answer}."
                            ),
                            source="web",
                            confidence=extracted_obj.confidence,
                            internal_notes=f"Web-retrieved information via LLM extraction. Confidence: {extracted_obj.confidence:.2f}",
                            resolved_attribute=canonical_attr,
                            resolved_value=extracted_obj.answer
                        )
                        await save_to_cache(cache_key, ans)
                        return ans
                    elif 0.50 <= extracted_obj.confidence < web_threshold:
                        if is_soft:
                            ans = ProductAnswer(
                                customer_response=(
                                    f"Regarding the {product.name}, the {canonical_attr or 'requested specification'} is {extracted_obj.answer}."
                                ),
                                source="general_knowledge",
                                confidence=extracted_obj.confidence,
                                internal_notes=(
                                    f"General Knowledge Estimate based on LLM web extraction.\n"
                                    f"Disclaimer: This is an estimate based on search results and not verified from the official product specifications catalog."
                                ),
                                resolved_attribute=canonical_attr,
                                resolved_value=extracted_obj.answer
                            )
                            await save_to_cache(cache_key, ans)
                            return ans
            except Exception as e:
                logger.error("LLM web extraction failed: %s", e)        # --- LEVEL 2: Metadata / Attribute Inference ---
        # Route natural-language sales, comparison, recommendation, and concern
        # questions directly to the appropriate sales metadata fields.
        # All responses use conversational wrappers — no raw field names or JSON.
        inferred_ans = None
        inferred_notes = ""

        if sales_metadata:
            ideal_customer = sales_metadata.get("ideal_customer", "")
            use_cases = sales_metadata.get("use_cases", [])
            key_advantages = sales_metadata.get("key_advantages", [])
            objection = sales_metadata.get("objection_handling", {})

            # --- Who buys / target customer ---
            if any(p in q_lower for p in [
                "who buys", "who typically", "who usually", "who is this for",
                "who is the target", "target customer", "who purchases",
                "who would buy", "who should buy",
            ]):
                top_seg = ideal_customer.split(",")[0].strip() if "," in ideal_customer else ideal_customer
                inferred_ans = (
                    f"This tends to be a popular choice among {top_seg}. "
                    f"Does that match your team's profile?"
                )
                inferred_notes = "Level 2: Target segment resolved from sales metadata"

            # --- Why buy / recommendation / worth it ---
            elif any(p in q_lower for p in [
                "why buy", "why should i", "why choose", "would you recommend",
                "is it worth", "worth buying", "good choice", "worth it",
                "should i buy", "would this be a good",
            ]):
                top_3 = key_advantages[:3]
                bullets = "\n".join(f"• {a}" for a in top_3)
                inferred_ans = (
                    f"A few reasons customers tend to choose this:\n{bullets}\n\n"
                    f"Want me to dig into any of these?"
                )
                inferred_notes = "Level 2: Recommendation resolved from key_advantages"

            # --- What makes it stand out / differentiator / highlights ---
            elif any(p in q_lower for p in [
                "stand out", "what makes", "differentiator", "unique", "highlight",
                "advantage", "what's special", "what is special",
            ]):
                top_3 = key_advantages[:3]
                bullets = "\n".join(f"• {a}" for a in top_3)
                inferred_ans = (
                    f"Here's what tends to set this apart:\n{bullets}\n\n"
                    f"Anything specific you'd like to know more about?"
                )
                inferred_notes = "Level 2: Differentiators resolved from key_advantages"

            # --- Downsides / concerns / limitations ---
            elif any(p in q_lower for p in [
                "downside", "limitation", "drawback", "cons", "problem",
                "issue", "weakness", "any concerns", "i should know",
            ]):
                top_use = use_cases[0] if use_cases else "everyday use"
                top_adv = key_advantages[0] if key_advantages else "solid reliability"
                inferred_ans = (
                    f"No product is perfect for every scenario. This one is optimised for {top_use}, "
                    f"where {top_adv.lower()} is a real strength. "
                    f"If your requirements are very different, I'd be happy to help evaluate the fit."
                )
                inferred_notes = "Level 2: Limitation/concern handled from use_cases and advantages"

            # --- Comparison / alternatives ---
            elif any(p in q_lower for p in [
                "compare", "how does this", "how is this different", "alternative",
                "vs ", " vs", "versus", "better than",
            ]):
                top_3 = key_advantages[:3]
                bullets = "\n".join(f"• {a}" for a in top_3)
                inferred_ans = (
                    f"Compared to alternatives in this space, this model holds its own particularly on:\n{bullets}\n\n"
                    f"Would you like to do a side-by-side comparison with a specific product?"
                )
                inferred_notes = "Level 2: Comparison handled from key_advantages"

            # --- Good for travel / portable ---
            elif any(p in q_lower for p in [
                "travel", "portable", "portability", "on the go", "take it anywhere",
                "lightweight",
            ]):
                travel_case = next(
                    (c for c in use_cases if any(k in c.lower() for k in ["travel", "portable", "go", "outdoor", "commut"])),
                    use_cases[0] if use_cases else None
                )
                if travel_case:
                    inferred_ans = (
                        f"Yes — portability is one of the strengths here. "
                        f"Customers often choose this for {travel_case.lower()}. "
                        f"Is this for personal travel or a team deployment?"
                    )
                else:
                    inferred_ans = (
                        f"Portability depends on your specific needs. "
                        f"Let me know what you have in mind and I can give you a more specific answer."
                    )
                inferred_notes = "Level 2: Travel/portability resolved from use_cases"

            # --- Good for students / specific audiences ---
            elif any(p in q_lower for p in [
                "student", "students", "education", "school", "university", "college",
            ]):
                edu_case = next(
                    (c for c in use_cases if any(k in c.lower() for k in ["student", "education", "learning", "study"])),
                    None
                )
                seg_match = "student" in ideal_customer.lower() or "education" in ideal_customer.lower()
                if edu_case or seg_match:
                    inferred_ans = (
                        f"Yes, students are among the key users for this. "
                        f"It works particularly well for {edu_case.lower() if edu_case else 'academic and personal use'}. "
                        f"Are you evaluating this for individual students or a department purchase?"
                    )
                else:
                    inferred_ans = (
                        f"It can work for students depending on the use case. "
                        f"What specifically are they looking to use it for?"
                    )
                inferred_notes = "Level 2: Student/education suitability resolved from metadata"

            # --- Good for professionals / enterprise / business ---
            elif any(p in q_lower for p in [
                "professional", "enterprise", "business use", "office", "corporate",
                "team use", "business team",
            ]):
                top_seg = ideal_customer.split(",")[0].strip() if "," in ideal_customer else ideal_customer
                top_case = use_cases[0] if use_cases else "professional use"
                inferred_ans = (
                    f"Absolutely — this is well suited for {top_seg}. "
                    f"Most teams use it for {top_case.lower()}. "
                    f"How many units are you considering?"
                )
                inferred_notes = "Level 2: Professional/enterprise suitability resolved from metadata"

            # --- Is it good for X / suitable for X / best for X ---
            elif any(p in q_lower for p in [
                "good for", "suitable for", "perfect for", "ideal for", "best for",
                "work for", "use for",
            ]):
                top_2 = use_cases[:2]
                cases_str = " and ".join(c.lower() for c in top_2) if len(top_2) > 1 else top_2[0].lower() if top_2 else "everyday use"
                inferred_ans = (
                    f"It tends to work especially well for {cases_str}. "
                    f"Is that the kind of scenario you have in mind?"
                )
                inferred_notes = "Level 2: Use-case suitability resolved from use_cases"

            # --- General use cases / scenarios ---
            elif any(p in q_lower for p in [
                "use case", "use for", "scenario", "where can", "applications",
            ]):
                top_2 = use_cases[:2]
                cases_str = " and ".join(c.lower() for c in top_2) if len(top_2) > 1 else top_2[0].lower() if top_2 else "everyday use"
                inferred_ans = (
                    f"This works really well for {cases_str}. "
                    f"Is that the kind of scenario you have in mind?"
                )
                inferred_notes = "Level 2: Use cases resolved from sales metadata"

            # --- Price / value for money ---
            elif any(p in q_lower for p in [
                "price", "expensive", "cost", "value for money", "worth the price",
                "good value", "affordable", "budget",
            ]):
                inferred_ans = objection.get("price", "")
                if inferred_ans:
                    inferred_ans += "\n\nWould you like to discuss volume pricing?"
                inferred_notes = "Level 2: Pricing objection resolved from sales metadata"

            # --- Warranty ---
            elif any(p in q_lower for p in ["warranty", "guarantee", "after-sales", "support plan"]):
                inferred_ans = objection.get("warranty", "")
                inferred_notes = "Level 2: Warranty concern resolved from sales metadata"

            # --- Maintenance ---
            elif any(p in q_lower for p in [
                "maintenance", "upkeep", "clean", "repair", "service",
            ]):
                inferred_ans = objection.get("maintenance", "")
                inferred_notes = "Level 2: Maintenance concern resolved from sales metadata"

            # --- Compatibility ---
            elif any(p in q_lower for p in [
                "compatible", "compatibility", "work with", "integration",
            ]):
                inferred_ans = objection.get("compatibility", "")
                inferred_notes = "Level 2: Compatibility concern resolved from sales metadata"

            # --- Longevity / durability ---
            elif any(p in q_lower for p in [
                "longevity", "durable", "how long", "lifetime", "last long",
            ]):
                inferred_ans = objection.get("longevity", "")
                inferred_notes = "Level 2: Longevity concern resolved from sales metadata"

        if inferred_ans and inferred_ans.strip():
            logger.info("[DIAGNOSTICS - SPECIFICATION RETRIEVAL] Level 2 Inference Successful: %s", inferred_notes)
            ans = ProductAnswer(
                customer_response=inferred_ans.strip(),
                source="general_knowledge",
                confidence=0.85,
                internal_notes=inferred_notes,
                resolved_attribute=canonical_attr,
                resolved_value=inferred_ans
            )
            await save_to_cache(cache_key, ans)
            return ans

        # --- LEVEL 3: LLM-Generated Consultative Estimate ---
        # Before calling the LLM, check if the question asks about a highly-specific
        # technical feature that cannot be verified from available metadata.
        # In that case, return an honest hedge rather than risk fabricating certainty.
        _HIGHLY_SPECIFIC_FEATURES = [
            "satellite", "lidar", "infrared", "5g mmwave", "mmwave", "usb4", "usb 4",
            "wi-fi 7", "wifi 7", "uwb", "ultra-wideband", "tof sensor", "depth sensor",
            "lte band", "frequency band", "sar rating", "mil-spec", "mil spec",
            "hdr10+", "dolby vision", "atmos", "quantum dot",
        ]
        feature_hit = next((f for f in _HIGHLY_SPECIFIC_FEATURES if f in q_lower), None)
        if feature_hit and is_strict:
            category_str = product.category or "this segment"
            hedge_text = (
                f"I couldn't verify {feature_hit} support for this specific model. "
                f"Products in {category_str} increasingly include capabilities like this, "
                f"but I'd recommend confirming the exact configuration before your procurement decision."
            )
            logger.info(
                "[DIAGNOSTICS - SPECIFICATION RETRIEVAL] Level 3 hedge triggered for feature: %s", feature_hit
            )
            ans = ProductAnswer(
                customer_response=hedge_text,
                source="general_knowledge",
                confidence=0.50,
                internal_notes=f"Level 3 hedge: highly specific feature '{feature_hit}' could not be verified.",
                resolved_attribute=canonical_attr,
                resolved_value=hedge_text
            )
            await save_to_cache(cache_key, ans)
            return ans

        # Generate a consultative LLM estimate. Use soft phrasing — never hallucinate certainty.
        logger.info(
            "[DIAGNOSTICS - SPECIFICATION RETRIEVAL] Triggering Level 3 Consultative LLM Estimate. "
            "Product: %s, Category: %s", product.name, product.category
        )

        # Prepare context data for LLM
        catalog_specs_text = "\n".join(f"- {name}: {val}" for name, val in spec_dict.items())
        metadata_summary = ""
        if sales_metadata:
            metadata_summary = (
                f"Ideal Customer: {sales_metadata.get('ideal_customer')}\n"
                f"Use Cases: {', '.join(sales_metadata.get('use_cases', []))}\n"
                f"Key Strengths: {', '.join(sales_metadata.get('key_advantages', []))}\n"
            )

        system_prompt = (
            "You are a knowledgeable, consultative sales rep. Answer the customer's product question naturally.\n"
            "RULES:\n"
            "1. NEVER say 'Specification unavailable', 'not found', or 'no data'.\n"
            "2. If unsure of a specific detail, use soft phrasing: 'typically', 'generally', 'usually', "
            "'most models in this range'. Do NOT invent specific numbers or model codes.\n"
            "3. Sound like a helpful salesperson — conversational, not corporate.\n"
            "4. Keep the response under 80 words. Use 2–3 short sentences. "
            "End with one follow-up question if possible. No long paragraphs.\n"
            "5. Do NOT use bullet points unless listing fewer than 4 items that genuinely need it.\n"
            "Return a JSON object with this schema:\n"
            "{\n"
            "  \"answer\": \"your conversational response\",\n"
            "  \"confidence\": 0.75\n"
            "}\n"
        )
        
        prompt = (
            f"Product Name: {product.name}\n"
            f"Category: {product.category}\n"
            f"Description: {product.description or 'No catalog description'}\n\n"
            f"Product Specifications Catalog:\n{catalog_specs_text}\n\n"
            f"Product Sales Intelligence:\n{metadata_summary}\n\n"
            f"Customer Question: {question}\n\n"
            f"Generate a consultative, soft-phrased estimate matching B2B standards in JSON format."
        )

        try:
            class Level3Answer(BaseModel):
                answer: str
                confidence: float

            llm_result = await self._llm.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                response_model=Level3Answer
            )
            
            # Verify the response is useful and doesn't contain unavailability phrases
            ans_clean = llm_result.answer
            unavail_phrases = ["specification unavailable", "information not found", "no information available", "no data available"]
            if not any(p in ans_clean.lower() for p in unavail_phrases) and len(ans_clean.strip()) > 5:
                ans = ProductAnswer(
                    customer_response=f"Regarding the {product.name}, {ans_clean}",
                    source="general_knowledge",
                    confidence=max(llm_result.confidence, 0.70),
                    internal_notes="Level 3: Consultative LLM estimate generated successfully.",
                    resolved_attribute=canonical_attr,
                    resolved_value=ans_clean
                )
                await save_to_cache(cache_key, ans)
                return ans
        except Exception as exc:
            logger.error("Level 3 Consultative LLM estimation failed: %s", exc)

        # --- LEVEL 4: Safe Category Recommendation / Fallback ---
        # Clean, category-based fallback that answers the question constructively.
        logger.info("[DIAGNOSTICS - SPECIFICATION RETRIEVAL] Level 4 Fallback Triggered.")
        
        category_lower = product.category.lower() if product.category else "general"
        if "electronics" in category_lower:
            fallback_text = "devices in this B2B segment are generally supplied with standard accessories, standard warranty coverage (typically 1 to 2 years), and are compatible with all main commercial setups. We can configure specific packaging options to fit your deployment scale."
        elif "apparel" in category_lower:
            fallback_text = "apparel products in our catalog are manufactured with standard commercial size curves (ranging from S to XXL) and quality fabric weaves designed to retain shape and color over commercial laundry cycles."
        elif "footwear" in category_lower:
            fallback_text = "footwear models in our supply line feature high-traction rubber soles, B2B size scales (US 6-13), and comfort insole paddings suited for all-day operational workloads."
        elif "books" in category_lower:
            fallback_text = "print books in this catalog category are supplied in standard library trim bindings (hardcover or high-quality softcover editions) and English language text layouts optimized for educational and reference libraries."
        elif "appliance" in category_lower:
            fallback_text = "appliances in our supply catalogue conform to standard power inputs, offer energy-efficient settings, and include manufacturer warranty coverage. We also provide direct B2B installation guidance."
        else:
            fallback_text = "catalog models in this category are designed for commercial-grade durability and standard plug-and-play setup. We back these with comprehensive warranty terms and can tailor delivery to your business site requirements."

        ans = ProductAnswer(
            customer_response=f"Regarding the {product.name}, {fallback_text}",
            source="general_knowledge",
            confidence=0.60,
            internal_notes="Level 4: Safe category-driven recommendation fallback.",
            resolved_attribute=canonical_attr,
            resolved_value=fallback_text
        )
        await save_to_cache(cache_key, ans)
        return ans

    async def compare_products(
        self,
        query: str,
        active_product: Product | None,
        db: AsyncSession,
    ) -> dict[str, Any]:
        """Perform side-by-side catalog comparison for products mentioned in the query."""
        resolver = ProductResolver(llm=self._llm)
        resolved = await resolver.resolve_products(query, db)

        # Include the active product in comparison if it's not already resolved
        if active_product and active_product.id not in [p.id for p in resolved]:
            resolved.append(active_product)

        # Cap comparison to 3 products
        products_to_compare = resolved[:3]

        comparison_data = []
        all_spec_names = set()

        for prod in products_to_compare:
            stmt = select(ProductSpecification).where(ProductSpecification.product_id == prod.id)
            res = await db.execute(stmt)
            specs = res.scalars().all()

            if not specs:
                logger.info("Self-healing specifications during comparison for product: %s", prod.name)
                from app.services.product_intelligence_generator import generate_specs_for_product
                generated_specs = generate_specs_for_product(prod)
                specs_to_add = []
                for s_name, s_val in generated_specs.items():
                    spec_obj = ProductSpecification(
                        id=uuid.uuid4(),
                        product_id=prod.id,
                        specification_name=s_name,
                        specification_value=s_val
                    )
                    db.add(spec_obj)
                    specs_to_add.append(spec_obj)
                await db.commit()
                specs = specs_to_add

            prod_specs = {}
            for s in specs:
                name_clean = s.specification_name.strip()
                if name_clean.lower() != "_sales_metadata_":
                    prod_specs[name_clean] = s.specification_value

            for name in prod_specs.keys():
                all_spec_names.add(name)

            comparison_data.append({
                "id": prod.external_product_id or str(prod.id),
                "name": prod.name,
                "price": prod.selling_price,
                "stock": prod.stock_quantity,
                "popularity": round((prod.popularity_index or 0.0) / 20.0, 1),
                "return_rate": prod.return_rate or 0.0,
                "category": prod.category,
                "specifications": prod_specs
            })

        return {
            "resolved_count": len(products_to_compare),
            "spec_names": list(all_spec_names),
            "products": comparison_data
        }

    async def explain_product(
        self,
        product: Product,
        question: str,
    ) -> ProductAnswer:
        """Provide an educational explanation of the product's working principles and usage.
        Does not mention price or other commercial terms.
        """
        system_prompt = (
            "You are an expert product specialist. Your goal is to explain how a product works, "
            "its features, its usage, or its working principle. Be educational, helpful, and concise.\n"
            "CRITICAL: Do NOT mention any pricing, discounts, lists, or commercial terms in your response.\n"
            "Return a JSON object conforming exactly to this schema:\n"
            "{\n"
            "  \"answer\": \"educational explanation of the product or how it works\",\n"
            "  \"confidence\": 1.0,\n"
            "  \"reasoning\": \"explanation of the product explanation\"\n"
            "}\n"
        )
        
        prompt = (
            f"Product Name: {product.name}\n"
            f"Product Category: {product.category}\n"
            f"Product Description: {product.description or 'No catalog description'}\n"
            f"Customer Question: {question}\n\n"
            f"Please explain how this product works or is used in an educational tone."
        )
        
        try:
            class ProductExplanationOutput(BaseModel):
                answer: str
                confidence: float
                reasoning: str

            result = await self._llm.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                response_model=ProductExplanationOutput,
            )
            return ProductAnswer(
                customer_response=result.answer,
                source="general_knowledge",
                confidence=result.confidence,
                internal_notes=f"Product explanation generated: {result.reasoning}"
            )
        except Exception as e:
            logger.error("Failed to generate product explanation: %s", e)
            return ProductAnswer(
                customer_response=f"The {product.name} is designed for optimal performance in its category. It works by utilizing standard operational features to achieve its described functions.",
                source="none",
                confidence=0.5,
                internal_notes=f"Fallback product explanation due to error: {e!s}"
            )
