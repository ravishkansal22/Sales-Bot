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

        # Lazy Self-Healing Generation: if no specifications exist for this product,
        # generate them dynamically on-the-fly and persist them permanently.
        # This keeps database load fast and backfills existing records seamlessly.
        if not specs:
            logger.info(
                "[DIAGNOSTICS - SPECIFICATION RETRIEVAL] Self-healing initiated: "
                "generating specifications for Product %s (%s)",
                product.name, str(product.id)
            )
            from app.services.product_intelligence_generator import generate_specs_for_product
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

        # Exclude special sales metadata from generic user-facing spec_dict
        spec_dict = {}
        sales_metadata = {}
        for s in specs:
            name_lower = s.specification_name.lower().strip()
            if name_lower == "_sales_metadata_":
                try:
                    sales_metadata = json.loads(s.specification_value)
                except Exception as e:
                    logger.warning("Failed to parse sales metadata JSON: %s", e)
            else:
                spec_dict[name_lower] = s.specification_value

        # Add catalog fields to spec dict
        spec_dict["category"] = product.category
        spec_dict["price"] = f"INR {product.selling_price:,.2f}"
        spec_dict["stock"] = f"{product.stock_quantity} units available"
        spec_dict["popularity"] = f"{round((product.popularity_index or 0.0) / 20.0, 1)}/5.0"
        spec_dict["return rate"] = f"{round(product.return_rate or 0.0, 2)}%"

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

        if matched_spec_name and matched_spec_val:
            logger.info(
                "[DIAGNOSTICS - SPECIFICATION RETRIEVAL] Catalog Match Found. Spec Name: '%s', Value: '%s'",
                matched_spec_name, matched_spec_val
            )
            return ProductAnswer(
                customer_response=(
                    f"Regarding the {product.name}, the official database record indicates:\n"
                    f"- **{matched_spec_name.title()}**: {matched_spec_val}\n\n"
                    f"Is there anything else you would like to know or negotiate?"
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
        # Look up standard B2B objections, use cases, customer segments, advantages,
        # or attributes inside sales_metadata and specs.
        inferred_ans = None
        inferred_notes = ""
        
        if sales_metadata:
            # Match pricing objections
            if "price" in q_lower or "expensive" in q_lower or "cost" in q_lower or "discount" in q_lower:
                inferred_ans = sales_metadata.get("objection_handling", {}).get("price")
                inferred_notes = "Level 2: Pricing objection resolved from sales metadata"
            # Match warranty concerns
            elif "warranty" in q_lower or "guarantee" in q_lower:
                inferred_ans = sales_metadata.get("objection_handling", {}).get("warranty")
                inferred_notes = "Level 2: Warranty concern resolved from sales metadata"
            # Match maintenance concerns
            elif "maintenance" in q_lower or "service" in q_lower or "clean" in q_lower or "repair" in q_lower:
                inferred_ans = sales_metadata.get("objection_handling", {}).get("maintenance")
                inferred_notes = "Level 2: Maintenance concern resolved from sales metadata"
            # Match compatibility concerns
            elif "compatibility" in q_lower or "compatible" in q_lower or "work with" in q_lower or "support" in q_lower:
                inferred_ans = sales_metadata.get("objection_handling", {}).get("compatibility")
                inferred_notes = "Level 2: Compatibility concern resolved from sales metadata"
            # Match longevity concerns
            elif "longevity" in q_lower or "durable" in q_lower or "last" in q_lower or "lifetime" in q_lower:
                inferred_ans = sales_metadata.get("objection_handling", {}).get("longevity")
                inferred_notes = "Level 2: Longevity concern resolved from sales metadata"
            # Match customer segment queries
            elif "customer" in q_lower or "who buys" in q_lower or "target" in q_lower or "segment" in q_lower:
                inferred_ans = f"This product is highly popular among {sales_metadata.get('ideal_customer')}."
                inferred_notes = "Level 2: Target segment resolved from sales metadata"
            # Match use cases
            elif "use case" in q_lower or "scenario" in q_lower or "where can I use" in q_lower or "suitable for" in q_lower:
                cases_str = ", ".join(sales_metadata.get("use_cases", []))
                inferred_ans = f"Typical deployment and use cases for this model include: {cases_str}."
                inferred_notes = "Level 2: Use cases resolved from sales metadata"
            # Match highlights/advantages
            elif "advantage" in q_lower or "why buy" in q_lower or "highlight" in q_lower or "stand out" in q_lower or "feature" in q_lower:
                advs_str = "\n".join(f"• {adv}" for adv in sales_metadata.get("key_advantages", []))
                inferred_ans = f"Here are the major highlights and advantages of selecting this model:\n{advs_str}"
                inferred_notes = "Level 2: Key advantages resolved from sales metadata"

        if inferred_ans:
            logger.info("[DIAGNOSTICS - SPECIFICATION RETRIEVAL] Level 2 Inference Successful: %s", inferred_notes)
            ans = ProductAnswer(
                customer_response=f"Regarding the {product.name}:\n\n{inferred_ans}",
                source="general_knowledge",
                confidence=0.85,
                internal_notes=inferred_notes,
                resolved_attribute=canonical_attr,
                resolved_value=inferred_ans
            )
            await save_to_cache(cache_key, ans)
            return ans

        # --- LEVEL 3: LLM-Generated Consultative Estimate ---
        # Generate a consultative response. We use soft phrasing like "is typically"
        # or "is generally" instead of hallucinating absolute certainty.
        logger.info(
            "[DIAGNOSTICS - SPECIFICATION RETRIEVAL] Triggering Level 3 Consultative LLM Estimate. "
            "Product: %s, Category: %s", product.name, product.category
        )
        
        # Prepare context data for LLM
        catalog_specs_text = "\n".join(f"- {name}: {val}" for name, val in spec_dict.items())
        metadata_summary = ""
        if sales_metadata:
            metadata_summary = (
                f"Ideal Customer Segments: {sales_metadata.get('ideal_customer')}\n"
                f"Use Cases: {', '.join(sales_metadata.get('use_cases', []))}\n"
                f"Key Advantages: {', '.join(sales_metadata.get('key_advantages', []))}\n"
            )

        system_prompt = (
            "You are a consultative B2B sales consultant. Your task is to answer a customer's product question "
            "using available catalog specifications, description, and B2B sales metadata.\n"
            "CRITICAL RULES:\n"
            "1. NEVER return 'Specification unavailable', 'Information not found', or 'No data available'.\n"
            "2. If you are not 100% certain, do NOT make up precise technical details. Instead, use soft, "
            "consultative phrasing (e.g. 'Products in this category are typically supplied with...', "
            "'This model generally includes...', 'For this type of equipment, standard configurations usually offer...').\n"
            "3. Keep the response professional, helpful, and focused on driving B2B value.\n"
            "Return a JSON object conforming exactly to this schema:\n"
            "{\n"
            "  \"answer\": \"your consultative answer or estimate\",\n"
            "  \"confidence\": 0.75  // float between 0.0 and 1.0\n"
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
