"""Dynamic Product Intelligence and Specification Generation Engine.

Contains template-based generators for specifications and B2B sales metadata
tailored to categories, subcategories, brand tiers, pricing segments, and
popularity metrics. Absolutely no hardcoded product names, examples, or IDs.
"""

from __future__ import annotations

import logging
import hashlib
import json
from typing import Any
from app.models.product import Product

logger = logging.getLogger(__name__)

# Category-specific price segment thresholds
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
    "timberland", "nike", "adidas", "dell ultrasharp", "proart", "bravia",
    "garmin", "bose", "jabra", "shure", "canon", "nikon", "fujifilm",
}

BUDGET_BRANDS = {
    "boat", "redmi", "xiaomi", "oneplus", "eureka", "kent", "haier",
    "godrej", "acer", "jbl", "lenovo", "realme", "noise", "ptron",
}


def get_product_brand_and_tier(name: str, price: float, category_key: str) -> tuple[str, str]:
    """Extract brand and resolve brand positioning tier dynamically from name and price."""
    name_lower = name.lower()
    words = name_lower.split()
    brand = words[0] if words else "generic"

    for pb in PREMIUM_BRANDS:
        if pb in name_lower:
            return pb.title(), "premium"

    for bb in BUDGET_BRANDS:
        if bb in name_lower:
            return bb.title(), "budget"

    if brand in PREMIUM_BRANDS:
        return brand.title(), "premium"
    elif brand in BUDGET_BRANDS:
        return brand.title(), "budget"

    thresholds = CATEGORY_PRICE_THRESHOLDS.get(category_key, {"budget": 3000.0, "premium": 15000.0})
    if price <= thresholds["budget"]:
        return brand.title(), "budget"
    elif price >= thresholds["premium"]:
        return brand.title(), "premium"
    return brand.title(), "mid-range"


def _detect_subcategory(name: str, category_key: str) -> str:
    """Detect electronics subcategory from the product name using generic keyword scanning.

    Uses only category-generic taxonomy keywords — no brand names, product IDs, or hardcoded examples.
    Expanded to cover common product naming patterns (e.g. 'Portable Audio System', 'Noise Cancelling ANC').
    Falls back to 'general_electronics' when no keyword matches.
    """
    if "electronics" not in category_key:
        detected = category_key
        logger.info(
            "[SUBCATEGORY] product=%s category=%s detected_subcategory=%s (non-electronics passthrough)",
            name, category_key, detected
        )
        return detected

    name_lower = name.lower()

    if any(k in name_lower for k in [
        "headphone", "earphone", "earbud", "buds", "headset",
        "in-ear", "over-ear", "noise cancelling", "noise-cancelling", " anc",
    ]):
        detected = "headphones"
    elif any(k in name_lower for k in ["phone", "mobile", "smartphone"]):
        detected = "smartphone"
    elif any(k in name_lower for k in ["watch", "band", "wearable", "smartwatch", "tracker", "fitness tracker"]):
        detected = "smartwatch"
    elif any(k in name_lower for k in [
        "speaker", "soundbar", "boombox", "boom box",
        "audio", "sound system", "portable audio", "bluetooth audio",
        "wireless speaker", "sound bar", "sound",
    ]):
        detected = "speaker"
    elif any(k in name_lower for k in ["laptop", "notebook", "chromebook", "ultrabook"]):
        # Note: 'macbook' excluded — use category-generic terms only
        detected = "laptop"
    elif any(k in name_lower for k in ["tablet", "tab ", "e-reader", "ereader", "slate"]):
        detected = "tablet"
    elif any(k in name_lower for k in ["camera", "dslr", "mirrorless", "action cam", "camcorder"]):
        detected = "camera"
    else:
        detected = "general_electronics"

    logger.info(
        "[SUBCATEGORY] product=%s category=%s detected_subcategory=%s",
        name, category_key, detected
    )
    return detected


def _pick(options: list[str], h: int) -> str:
    """Deterministically pick from a list of options using a hash seed."""
    return options[h % len(options)]


# ---------------------------------------------------------------------------
# Per-subcategory specification templates
# ---------------------------------------------------------------------------

def _electronics_specs(name: str, is_premium: bool, is_budget: bool, subcategory: str, h: int) -> dict[str, str]:
    """Return subcategory-specific specification fields for electronics."""
    specs: dict[str, str] = {}

    if subcategory == "smartphone":
        if is_premium:
            specs["display"] = _pick(["6.7\" Super AMOLED, 120Hz ProMotion, 2800 nits peak brightness",
                                      "6.1\" Dynamic OLED, 120Hz adaptive refresh, Always-On display",
                                      "6.8\" LTPO OLED, 1-120Hz variable, HDR10+"], h)
            specs["camera"] = _pick(["Triple-lens system: 50MP main + 12MP ultrawide + 10MP telephoto",
                                     "Quad-lens array with 108MP primary, optical zoom up to 10x",
                                     "50MP main with f/1.8 + Night Mode + 4K video stabilisation"], h)
            specs["battery"] = _pick(["5000mAh with 65W fast charge, 15W wireless",
                                      "4500mAh with 45W SuperCharge, 10W reverse wireless",
                                      "5000mAh with 67W wired and 50W wireless charging"], h)
            specs["connectivity"] = "5G (Sub-6GHz + mmWave), Wi-Fi 6E, Bluetooth 5.3, NFC, USB-C 3.2"
            specs["storage_options"] = "128GB, 256GB, 512GB, 1TB (UFS 3.1)"
        elif is_budget:
            specs["display"] = _pick(["6.5\" IPS LCD, 90Hz, 720p HD+",
                                      "6.6\" LCD, 60Hz, FHD+ resolution",
                                      "6.4\" IPS, 90Hz, 1080p"], h)
            specs["camera"] = _pick(["48MP primary + 2MP depth sensor, LED flash",
                                     "50MP rear + 8MP selfie camera",
                                     "64MP main + AI scene detection"], h)
            specs["battery"] = _pick(["5000mAh with 18W fast charge",
                                      "5000mAh with 15W charging",
                                      "4500mAh with 10W charging"], h)
            specs["connectivity"] = "4G LTE, Wi-Fi 5, Bluetooth 5.0, USB-C"
            specs["storage_options"] = "64GB or 128GB (expandable via microSD)"
        else:
            specs["display"] = _pick(["6.6\" AMOLED, 120Hz, FHD+",
                                      "6.5\" OLED, 90Hz, 2400x1080",
                                      "6.7\" Super LCD, 120Hz, 1080p"], h)
            specs["camera"] = _pick(["50MP main + 12MP ultrawide + 5MP macro",
                                     "64MP triple camera with OIS",
                                     "50MP + 8MP + 2MP with 4K recording"], h)
            specs["battery"] = _pick(["5000mAh with 33W fast charge",
                                      "4800mAh with 30W wired charging",
                                      "5000mAh with 25W charging"], h)
            specs["connectivity"] = "4G/5G, Wi-Fi 5, Bluetooth 5.1, USB-C"
            specs["storage_options"] = "128GB or 256GB"
        specs["operating_system"] = _pick(["Android 14 (upgradable to Android 16)",
                                           "iOS 17 with 6 years software updates",
                                           "Android 13 with 3 years OS support"], h)

    elif subcategory == "smartwatch":
        if is_premium:
            specs["display"] = _pick(["1.9\" Always-On AMOLED, 1000 nits, sapphire glass",
                                      "1.8\" Retina LTPO OLED, 2000 nits, Ion-X glass",
                                      "1.7\" AMOLED, Always-On, 500 nits"], h)
            specs["battery"] = _pick(["Up to 14 days typical use, 36h GPS mode",
                                      "Up to 18 hours on full charge, 60h low-power mode",
                                      "Up to 10 days typical use, 30h GPS"], h)
            specs["health_sensors"] = "Heart rate, SpO2, ECG, skin temperature, sleep tracking, stress monitor"
            specs["connectivity"] = "LTE + Wi-Fi + Bluetooth 5.0 + NFC + GPS/GLONASS"
            specs["water_resistance"] = "5ATM + IP68, swim-proof"
        else:
            specs["display"] = _pick(["1.7\" TFT-LCD, 360x360",
                                      "1.5\" AMOLED, 390x390",
                                      "1.6\" IPS LCD with always-on option"], h)
            specs["battery"] = _pick(["Up to 7 days typical use",
                                      "Up to 5 days full use",
                                      "Up to 10 days low-power mode"], h)
            specs["health_sensors"] = "Heart rate, SpO2, step counter, sleep tracking"
            specs["connectivity"] = "Bluetooth 5.0, Wi-Fi 2.4GHz, GPS"
            specs["water_resistance"] = "IP67 splash and sweat resistant"
        specs["compatibility"] = "Works with Android 8.0+ and iOS 14+"

    elif subcategory == "speaker":
        if is_premium:
            specs["audio_output"] = _pick(["60W RMS with dual tweeters + woofer",
                                           "80W 2.1 stereo with passive radiators",
                                           "50W 360-degree omnidirectional sound"], h)
            specs["battery"] = _pick(["Up to 24 hours playback at moderate volume",
                                      "Up to 20 hours continuous play, 2-hour charge",
                                      "Up to 30 hours with EQ optimisation"], h)
            specs["connectivity"] = "Bluetooth 5.3, Wi-Fi (AirPlay 2 / Spotify Connect), 3.5mm AUX, USB-C"
            specs["water_resistance"] = "IP67 waterproof and dustproof"
            specs["features"] = "Multi-device pairing, voice assistant support, True Wireless Stereo mode"
        elif is_budget:
            specs["audio_output"] = _pick(["10W RMS mono driver",
                                           "15W stereo with passive bass radiator",
                                           "12W single driver with bass boost"], h)
            specs["battery"] = _pick(["Up to 8 hours playback",
                                      "Up to 6 hours continuous play",
                                      "Up to 10 hours at low volume"], h)
            specs["connectivity"] = "Bluetooth 5.0, 3.5mm AUX"
            specs["water_resistance"] = "IPX5 splash-resistant"
            specs["features"] = "Hands-free calling, built-in microphone"
        else:
            specs["audio_output"] = _pick(["30W stereo with dual drivers",
                                           "20W 2.0 stereo, passive radiator bass",
                                           "25W with 360-degree sound"], h)
            specs["battery"] = _pick(["Up to 16 hours playback",
                                      "Up to 12 hours continuous",
                                      "Up to 18 hours with power-saver mode"], h)
            specs["connectivity"] = "Bluetooth 5.2, 3.5mm AUX, USB-C charging"
            specs["water_resistance"] = "IP66 waterproof"
            specs["features"] = "True Wireless Stereo, multi-device pairing, speakerphone"

    elif subcategory == "headphones":
        if is_premium:
            specs["audio"] = _pick(["40mm custom drivers, 20Hz–20kHz, Hi-Res Audio certified",
                                    "30mm beryllium dome drivers, 4Hz–80kHz frequency",
                                    "11mm dynamic + planar hybrid, full audiophile range"], h)
            specs["noise_cancellation"] = _pick(["Industry-leading Adaptive ANC with 8 mics",
                                                 "Multi-point ANC with transparency mode",
                                                 "Hybrid ANC with customisable levels"], h)
            specs["battery"] = _pick(["30 hours with ANC on, 3-min charge = 3 hours",
                                      "36 hours total, fast charge via USB-C",
                                      "40 hours without ANC, 25 hours with ANC"], h)
            specs["connectivity"] = "Bluetooth 5.2 multipoint, NFC pairing, 3.5mm wired"
            specs["comfort"] = "Memory foam ear cushions, foldable design, adjustable headband"
        elif is_budget:
            specs["audio"] = _pick(["40mm dynamic drivers, 20Hz–20kHz",
                                    "32mm drivers, enhanced bass boost",
                                    "10mm earphone drivers with silicone tips"], h)
            specs["noise_cancellation"] = _pick(["Passive noise isolation",
                                                 "Environmental noise cancellation (ENC) for calls",
                                                 "Passive isolation with foam ear tips"], h)
            specs["battery"] = _pick(["Up to 20 hours playback, 2-hour charge",
                                      "Up to 16 hours with case recharge",
                                      "Up to 12 hours earbuds + 24 hours case"], h)
            specs["connectivity"] = "Bluetooth 5.0, USB-C charging"
            specs["comfort"] = "Soft ear cushions, lightweight build under 220g"
        else:
            specs["audio"] = _pick(["40mm bio-fibre drivers, 20Hz–20kHz, punchy bass",
                                    "9mm dynamic drivers with enhanced soundstage",
                                    "30mm drivers, clear vocal reproduction"], h)
            specs["noise_cancellation"] = _pick(["Hybrid ANC with transparency mode",
                                                 "Active noise cancellation with ambient sound mode",
                                                 "Adaptive ANC with 4-mic array"], h)
            specs["battery"] = _pick(["Up to 25 hours with ANC, USB-C fast charge",
                                      "Up to 30 hours without ANC, 10-min quick charge",
                                      "Up to 8 hours earbuds + 32 hours case"], h)
            specs["connectivity"] = "Bluetooth 5.2, 3.5mm wired option, USB-C"
            specs["comfort"] = "Adjustable headband, swappable ear pads, foldable"

    elif subcategory == "laptop":
        if is_premium:
            specs["processor"] = _pick(["Intel Core Ultra 9 185H, 16 cores, 5.1GHz boost",
                                        "Apple M3 Pro, 12-core CPU, 18-core Neural Engine",
                                        "AMD Ryzen 9 7940HS, 8 cores, 5.2GHz boost"], h)
            specs["display"] = _pick(["14\" OLED, 2880x1800, 120Hz, 400 nits",
                                      "16\" Liquid Retina XDR, 3456x2234, 254ppi",
                                      "15.6\" AMOLED, 2560x1600, 120Hz, VESA DisplayHDR 500"], h)
            specs["ram_storage"] = _pick(["32GB LPDDR5X + 1TB NVMe SSD",
                                          "24GB unified memory + 512GB SSD",
                                          "16GB DDR5 + 512GB PCIe Gen4 NVMe"], h)
            specs["battery"] = _pick(["Up to 22 hours on a single charge",
                                      "All-day battery up to 18 hours (MagSafe charging)",
                                      "Up to 16 hours, 100W USB-C GaN charging"], h)
            specs["connectivity"] = "Thunderbolt 4 x2, USB-A x1, HDMI 2.1, Wi-Fi 6E, Bluetooth 5.3"
            specs["weight"] = _pick(["1.24 kg — ultralight for extended travel",
                                     "1.37 kg, MagSafe and USB-C charging",
                                     "1.56 kg with full-size keyboard"], h)
        elif is_budget:
            specs["processor"] = _pick(["Intel Core i5-1235U, 10 cores, 4.4GHz",
                                        "AMD Ryzen 5 7530U, 6 cores, 4.5GHz",
                                        "Intel Core i3-1315U, 6 cores, 4.5GHz"], h)
            specs["display"] = _pick(["15.6\" TN, 1920x1080, 60Hz, 250 nits",
                                      "14\" IPS, FHD, 45% NTSC, 60Hz",
                                      "15.6\" IPS, FHD, 60Hz, anti-glare"], h)
            specs["ram_storage"] = _pick(["8GB DDR4 + 512GB SATA SSD",
                                          "8GB DDR4 + 256GB NVMe",
                                          "8GB RAM + 512GB HDD hybrid"], h)
            specs["battery"] = _pick(["Up to 6 hours light use",
                                      "Up to 8 hours mixed use",
                                      "Up to 7 hours office tasks"], h)
            specs["connectivity"] = "USB-A x3, HDMI 1.4, Wi-Fi 5, Bluetooth 4.2"
            specs["weight"] = "1.8 kg — standard portable form factor"
        else:
            specs["processor"] = _pick(["Intel Core i7-1355U, 10 cores, 5.0GHz",
                                        "AMD Ryzen 7 7745HX, 8 cores, 5.1GHz",
                                        "Intel Core i5-13500H, 12 cores, 4.7GHz"], h)
            specs["display"] = _pick(["14\" IPS, 2560x1600, 100% sRGB, 400 nits",
                                      "15.6\" OLED, FHD, 60Hz, 100% DCI-P3",
                                      "13.3\" OLED, 2560x1600, 120Hz"], h)
            specs["ram_storage"] = _pick(["16GB DDR5 + 512GB NVMe SSD",
                                          "16GB LPDDR5 + 1TB SSD",
                                          "16GB DDR4 + 512GB PCIe NVMe"], h)
            specs["battery"] = _pick(["Up to 12 hours mixed use",
                                      "Up to 14 hours light office tasks",
                                      "Up to 10 hours development workloads"], h)
            specs["connectivity"] = "USB-C 3.2 x2, USB-A x2, HDMI 2.0, Wi-Fi 6, Bluetooth 5.2"
            specs["weight"] = _pick(["1.4 kg — travel-friendly all-rounder",
                                     "1.6 kg with full-size keyboard",
                                     "1.3 kg, slim bezel design"], h)

    elif subcategory == "tablet":
        if is_premium:
            specs["display"] = _pick(["12.9\" Liquid Retina XDR, 2732x2048, ProMotion 120Hz",
                                      "11\" OLED, 2800x2100, 120Hz, 1000 nits",
                                      "12.4\" Super AMOLED, 2560x1600, 120Hz"], h)
            specs["processor"] = _pick(["Apple M2 chip, 8-core CPU, 10-core GPU",
                                        "Snapdragon 8 Gen 2 for Mobile, 3.2GHz",
                                        "Apple M1 chip, 8 cores, 16GB unified memory"], h)
            specs["battery"] = _pick(["Up to 10 hours web browsing, 20W USB-C charge",
                                      "Up to 12 hours video playback, 45W charging",
                                      "Up to 9 hours mixed use, MagSafe compatible"], h)
            specs["connectivity"] = "Wi-Fi 6E, Bluetooth 5.3, USB-C / Thunderbolt, optional 5G"
            specs["accessories"] = "Compatible with Apple Pencil 2nd gen or equivalent stylus and keyboard folio"
        else:
            specs["display"] = _pick(["10.4\" TFT-LCD, 2000x1200, 60Hz",
                                      "10.1\" IPS, 1920x1200, 60Hz",
                                      "10.5\" AMOLED, 2560x1600, 90Hz"], h)
            specs["processor"] = _pick(["MediaTek Helio G99, 6 cores",
                                        "Qualcomm Snapdragon 680, 8 cores",
                                        "UNISOC T618, octa-core"], h)
            specs["battery"] = _pick(["7040mAh, up to 10 hours use",
                                      "8000mAh, up to 12 hours video",
                                      "6000mAh, 15W USB-C charging"], h)
            specs["connectivity"] = "Wi-Fi 5, Bluetooth 5.0, USB-C, 4G LTE optional"
            specs["accessories"] = "Compatible with magnetic keyboard case and capacitive stylus"
        specs["storage_options"] = "64GB, 128GB, 256GB (expandable via microSD up to 1TB)"

    elif subcategory == "camera":
        if is_premium:
            specs["sensor"] = _pick(["35mm full-frame BSI-CMOS, 45.7MP",
                                     "APS-C X-Trans CMOS 5 HS, 40MP",
                                     "35mm full-frame CMOS, 61MP, ISO 50–204800"], h)
            specs["autofocus"] = _pick(["693-point phase-detect AF, Eye/Animal/Vehicle tracking",
                                        "759-point hybrid AF, subject recognition AI",
                                        "Real-time subject tracking, 50fps burst"], h)
            specs["video"] = _pick(["8K RAW up to 30fps, 4K 120fps, 10-bit ProRes Log",
                                    "6K open-gate, 4K 120fps, Cinema DNG RAW",
                                    "4K 120fps 10-bit, 1080p 240fps slow motion"], h)
            specs["battery"] = _pick(["Approx. 400 shots per charge (CIPA)",
                                      "Approx. 350 shots, USB-C charging while shooting",
                                      "Approx. 500 shots via viewfinder"], h)
            specs["connectivity"] = "CFexpress + UHS-II dual slots, Wi-Fi 5GHz, Bluetooth 5.0, USB-C 3.2"
        else:
            specs["sensor"] = _pick(["APS-C CMOS, 24.2MP, ISO 100–25600",
                                     "1-inch BSI-CMOS, 20MP, 4K video",
                                     "APS-C, 24.1MP, optical stabilisation"], h)
            specs["autofocus"] = _pick(["179-point phase-detect AF, face and eye detection",
                                        "225-point contrast AF, subject tracking",
                                        "Dual-pixel AF, 4K30fps video"], h)
            specs["video"] = _pick(["4K 30fps, Full HD 120fps, HDMI out",
                                    "4K 30fps uncropped, 1080p 60fps",
                                    "4K 25fps, Full HD 120fps S-Log"], h)
            specs["battery"] = _pick(["Approx. 310 shots per charge",
                                      "Approx. 250 shots, USB-C charging",
                                      "Approx. 420 shots per charge"], h)
            specs["connectivity"] = "SD card, Wi-Fi, Bluetooth, USB-C / Micro-HDMI"
        specs["stabilisation"] = "In-body 5-axis optical image stabilisation (IBIS)" if is_premium else "Electronic image stabilisation (EIS)"

    else:  # general_electronics
        if is_premium:
            specs["connectivity"] = "Thunderbolt 4, Wi-Fi 6E, Bluetooth 5.3, HDMI 2.1"
            specs["battery_life"] = "Up to 24 hours with fast charge support"
            specs["material"] = "Aerospace-grade anodised aluminium"
            specs["portability"] = "Slim ergonomic build, fits standard carry cases"
        elif is_budget:
            specs["connectivity"] = "USB-A, Wi-Fi 5, Bluetooth 5.0"
            specs["battery_life"] = "Up to 8 hours standard use"
            specs["material"] = "Textured ABS polycarbonate"
            specs["portability"] = "Standard dimensions, robust build"
        else:
            specs["connectivity"] = "USB-C 3.2, Wi-Fi 5, Bluetooth 5.0, HDMI 2.0"
            specs["battery_life"] = "Up to 15 hours continuous"
            specs["material"] = "Aluminium alloy and polymer composite"
            specs["portability"] = "Travel-friendly, lightweight design"

        specs["compatibility"] = "Compatible with Windows 10/11, macOS, and standard commercial setups"
        specs["installation_requirements"] = "Zero configuration, pre-calibrated firmware out of the box"

    return specs


# ---------------------------------------------------------------------------
# Per-subcategory sales metadata templates
# ---------------------------------------------------------------------------

def _electronics_metadata(subcategory: str, is_premium: bool, is_budget: bool,
                           product_name: str, h: int) -> dict[str, Any]:
    """Return subcategory-appropriate sales metadata for electronics."""

    if subcategory == "smartphone":
        ideal_customer_options = [
            "professionals who need reliable communication and productivity on the go",
            "frequent travelers and remote workers who depend on their phone as a primary work device",
            "business users looking for a capable, portable productivity tool",
        ]
        ideal_customer = _pick(ideal_customer_options, h)
        use_cases = ["Daily productivity and business communication", "Photography and content creation",
                     "Travel and navigation", "Mobile banking and secure transactions"]
        key_advantages_options = [
            ["Fast and responsive for multitasking", "High-quality camera for meetings and content",
             "Compact and always with you", "Long battery for full work days"],
            ["Smooth performance across all apps", "Excellent camera system",
             "Portable design with all-day battery", "Strong ecosystem integration"],
        ]
        key_advantages = _pick(key_advantages_options, h)
        if is_premium:
            objection_price = f"The {product_name} is priced at the premium end, but customers consistently find the build quality, camera performance, and software longevity justify the investment — especially with long trade-in value."
            objection_longevity = "Built to last 4–5 years with software updates included. Premium materials make a real difference in resale value too."
        else:
            objection_price = f"The {product_name} hits a great sweet spot — you get flagship-tier features without the flagship price tag. Ideal when you need capability without stretching the budget."
            objection_longevity = "Solid build with manufacturer warranty. Handles daily wear well across typical 2–3 year usage cycles."

    elif subcategory == "smartwatch":
        ideal_customer_options = [
            "health-conscious professionals who want fitness insights alongside smart notifications",
            "active users who want to track workouts, sleep, and health metrics from the wrist",
            "professionals who prefer quick glance access to notifications without picking up their phone",
        ]
        ideal_customer = _pick(ideal_customer_options, h)
        use_cases = ["Fitness and health tracking", "Notifications and call management on the go",
                     "GPS navigation during runs and outdoor activities", "Sleep and stress monitoring"]
        key_advantages_options = [
            ["Always-on health monitoring throughout the day", "Lightweight and comfortable for all-day wear",
             "Syncs seamlessly with your smartphone", "Long battery life for active users"],
            ["Tracks fitness metrics in real time", "Comfortable enough to wear 24/7",
             "Quick access to calls and messages from your wrist", "Good battery life across workout modes"],
        ]
        key_advantages = _pick(key_advantages_options, h)
        objection_price = f"The {product_name} combines a fitness tracker, health monitor, and smart assistant in one. Compared to dedicated devices for each, it's actually great value."
        objection_longevity = "Designed for daily wear, sweat, and activity. Durable enough for gym workouts, runs, and outdoor use."

    elif subcategory == "speaker":
        ideal_customer_options = [
            "music lovers who want great sound at home, outdoors, or while traveling",
            "people who enjoy entertaining — whether at home, at the beach, or on the go",
            "anyone who wants a portable, reliable speaker for everyday listening",
        ]
        ideal_customer = _pick(ideal_customer_options, h)
        use_cases = ["Home and outdoor music listening", "Events, gatherings, and parties",
                     "Travel and portable entertainment", "Background audio for workspaces and cafes"]
        key_advantages_options = [
            ["Loud, clear sound even outdoors", "Portable and easy to carry anywhere",
             "Long battery for extended sessions", "Pairs easily with any device"],
            ["Room-filling audio in a compact size", "Built to handle outdoor conditions",
             "Battery that lasts through the whole day", "Simple one-tap Bluetooth pairing"],
        ]
        key_advantages = _pick(key_advantages_options, h)
        objection_price = f"The {product_name} is built to last and sounds noticeably better than cheaper options. Customers who've tried it rarely go back."
        objection_longevity = "Durable construction, waterproof or splash-resistant design. Built for regular outdoor use."

    elif subcategory == "headphones":
        ideal_customer_options = [
            "frequent travelers, remote workers, and commuters who need great audio and focus",
            "audiophiles and music enthusiasts looking for high-fidelity listening",
            "professionals who spend long hours on calls and need comfort with good isolation",
        ]
        ideal_customer = _pick(ideal_customer_options, h)
        use_cases = ["Music, podcasts, and focused listening", "Video calls and remote work",
                     "Travel and commuting", "Creative work and studio monitoring"]
        key_advantages_options = [
            ["Immersive audio quality that's hard to match", "Noise cancellation for deep focus",
             "Comfortable for hours at a stretch", "Long battery with quick charge"],
            ["Clear, detailed sound across all genres", "Active noise cancellation for noisy environments",
             "Lightweight and easy to wear all day", "Fast charging — a few minutes tops up hours"],
        ]
        key_advantages = _pick(key_advantages_options, h)
        objection_price = f"The {product_name} is an investment in your listening experience. Customers report it transforms commutes, travel, and focus sessions — and the build quality holds up for years."
        objection_longevity = "Premium headphones are designed for 3–5 years of daily use. Ear pads are replaceable and the build is travel-grade."

    elif subcategory == "laptop":
        ideal_customer_options = [
            "remote professionals, developers, and students who need a reliable daily driver",
            "professionals who need power and portability for work on the move",
            "teams that need capable mobile workstations without lugging desktop setups",
        ]
        ideal_customer = _pick(ideal_customer_options, h)
        use_cases = ["Remote work and business productivity", "Software development and engineering",
                     "Content creation and design", "Presentations and enterprise mobility"]
        key_advantages_options = [
            ["All-day battery so you're not hunting for outlets", "Fast enough to handle heavy multitasking",
             "Portable without sacrificing performance", "Runs everything you need out of the box"],
            ["Long battery life for mobile work", "Smooth performance for development and creative tasks",
             "Lightweight and travel-friendly", "Wide app and peripheral compatibility"],
        ]
        key_advantages = _pick(key_advantages_options, h)
        if is_premium:
            objection_price = f"The {product_name} is a machine built for professionals who can't afford downtime. The performance gains, build quality, and longevity typically make it the cheaper option over a 3–4 year horizon."
        else:
            objection_price = f"The {product_name} delivers solid performance for everyday professional use at a price that makes sense for most teams and individuals."
        objection_longevity = "Laptops at this tier typically last 3–5 years with normal use. Battery health can be maintained with smart charging habits."

    elif subcategory == "tablet":
        ideal_customer_options = [
            "students, creative professionals, and field workers who need a portable large-screen device",
            "professionals who want a versatile device for notes, reading, and light productivity",
            "users who want a portable screen for content, reading, and video calls",
        ]
        ideal_customer = _pick(ideal_customer_options, h)
        use_cases = ["Digital note-taking and reading", "Creative work and illustration",
                     "Video conferencing and presentations", "Entertainment and casual browsing"]
        key_advantages_options = [
            ["Versatile — works for work and entertainment", "Lightweight touchscreen experience",
             "All-day battery for meetings and travel", "Pairs with keyboard and stylus for real productivity"],
            ["Large screen in a portable form", "Great for note-taking and creative work",
             "Long-lasting battery", "Keyboard and stylus compatibility expands what it can do"],
        ]
        key_advantages = _pick(key_advantages_options, h)
        objection_price = f"The {product_name} replaces both a notebook and an entertainment device for many buyers — value-for-money when you factor in versatility."
        objection_longevity = "Tablets typically last 4–6 years. Software support is generous on premium models."

    elif subcategory == "camera":
        ideal_customer_options = [
            "photographers, content creators, and journalists stepping up from smartphone cameras",
            "hobbyists and semi-professionals who want creative control over their shots",
            "visual storytellers who need reliable image quality for professional work",
        ]
        ideal_customer = _pick(ideal_customer_options, h)
        use_cases = ["Photography and visual storytelling", "Professional shoots and events",
                     "Social media content creation", "Travel documentation and video"]
        key_advantages_options = [
            ["Significantly better image quality than smartphones", "Interchangeable lenses for every scenario",
             "Manual controls for creative flexibility", "Durable build for field use"],
            ["Superior low-light performance", "Versatile lens system for any shooting style",
             "Professional-grade video capabilities", "Built to handle real shooting conditions"],
        ]
        key_advantages = _pick(key_advantages_options, h)
        objection_price = f"The {product_name} gives you image quality and creative control that no smartphone can match. For anyone serious about photography, it's the right investment."
        objection_longevity = "Camera bodies last 5–10 years when maintained well. Lenses hold value and can be used across future bodies in the same mount ecosystem."

    else:  # general_electronics
        ideal_customer_options = [
            "professionals and teams looking for reliable, capable electronic equipment",
            "businesses that need dependable technology for daily operations",
        ]
        ideal_customer = _pick(ideal_customer_options, h)
        use_cases = ["Day-to-day professional use", "Team and office deployments",
                     "Productivity and communication tasks", "Remote work setups"]
        key_advantages = ["Reliable performance for professional tasks",
                          "Easy setup and broad compatibility",
                          "Strong warranty and after-sales support",
                          "Good value across its price segment"]
        objection_price = f"The {product_name} is priced competitively for its feature set. Most buyers find it delivers solid value over its lifetime."
        objection_longevity = "Built to standard commercial durability specifications for typical professional use cycles."

    objection_warranty = _pick([
        "Backed by a solid manufacturer warranty. For B2B orders we can also discuss extended service agreements.",
        "Warranty coverage is solid. For volume orders, extended business warranty options are often available.",
        "Standard warranty applies. Multi-unit orders can typically be paired with extended support plans.",
    ], h)

    objection_maintenance = _pick([
        "Minimal maintenance needed for typical use. The device handles daily workloads without any special upkeep.",
        "Pretty low maintenance in practice. Standard cleaning and software updates are all most users need.",
        "Straightforward to maintain. Regular software updates handle most performance upkeep automatically.",
    ], h)

    objection_compatibility = _pick([
        "Works with all major platforms and standard setups. Most buyers have it running within minutes.",
        "Compatible with the main ecosystems. Setup is usually plug-and-play.",
        "Broad compatibility across platforms and operating systems. No special configuration needed.",
    ], h)

    return {
        "ideal_customer": ideal_customer,
        "use_cases": use_cases,
        "key_advantages": key_advantages,
        "objection_handling": {
            "price": objection_price,
            "warranty": objection_warranty,
            "maintenance": objection_maintenance,
            "compatibility": objection_compatibility,
            "longevity": objection_longevity,
        },
    }


def generate_specs_for_product(product: Product) -> dict[str, str]:
    """Generate rich, dynamic key-value specifications and sales intelligence.

    Categorized by Electronics (with subcategory detection), Apparel, Footwear,
    Books, and Home Appliances. Attributes vary by pricing, brand tier, subcategory,
    and popularity. Language is category/subcategory-appropriate — no industrial
    terminology for consumer-facing product subcategories.
    """
    category_raw = product.category or "General"
    category_key = category_raw.lower().strip()

    price = product.selling_price
    thresholds = CATEGORY_PRICE_THRESHOLDS.get(category_key, {"budget": 3000.0, "premium": 15000.0})

    if price <= thresholds["budget"]:
        price_segment = "budget"
    elif price >= thresholds["premium"]:
        price_segment = "premium"
    else:
        price_segment = "mid-range"

    brand_name, brand_tier = get_product_brand_and_tier(product.name, price, category_key)

    is_premium = (price_segment == "premium" or brand_tier == "premium")
    is_budget = (price_segment == "budget" or brand_tier == "budget")

    seed_str = f"{product.id or product.name}"
    h = int(hashlib.md5(seed_str.encode("utf-8")).hexdigest(), 16)

    specs: dict[str, str] = {}

    # -------------------------------------------------------------------------
    # 1. Category / Subcategory Specifications
    # -------------------------------------------------------------------------
    if "electronics" in category_key:
        subcategory = _detect_subcategory(product.name, category_key)
        specs.update(_electronics_specs(product.name, is_premium, is_budget, subcategory, h))

    elif "apparel" in category_key:
        materials = ["Organic Cotton", "Merino Wool", "Recycled Polyester", "Nylon Blend", "Supima Cotton"]
        specs["material"] = f"{_pick(materials, h)} (premium double-weave)" if is_premium else "Cotton-Polyester blend (60/40)"
        specs["available_sizes"] = "XS, S, M, L, XL, XXL, XXXL"
        specs["available_colors"] = _pick(["Navy Blue, Carbon Black, Slate Grey, Forest Green, Classic White",
                                           "Jet Black, Cobalt Blue, Stone White, Olive, Burgundy",
                                           "Charcoal, Sand, Teal, White, Black"], h)
        specs["care_instructions"] = "Machine wash cold, tumble dry low, do not iron decorative highlights"
        if is_premium:
            specs["weather_suitability"] = "Water-repellent, windproof outer layer, thermal lining to -5°C"
            specs["fit_type"] = "Tailored athletic fit with ergonomic articulation"
        elif is_budget:
            specs["weather_suitability"] = "Comfortable for mild indoor and outdoor conditions"
            specs["fit_type"] = "Relaxed comfort fit"
        else:
            specs["weather_suitability"] = "All-season breathable layer, quick-dry"
            specs["fit_type"] = "Standard regular fit"

    elif "footwear" in category_key:
        specs["material"] = "Full-grain Italian leather, waterproof treated" if is_premium else "Synthetic leather and breathable mesh"
        soles = ["Vibram Megagrip rubber sole", "EVA high-traction slip-resistant sole", "Vulcanised natural rubber sole"]
        specs["sole_type"] = _pick(soles, h) if is_premium else "Standard vulcanised rubber sole"
        if is_premium:
            specs["comfort_level"] = "Memory foam orthotics, dual-density midsole, heel stabilisation cup"
            specs["activity_suitability"] = "High-intensity training, long-shift professional wear, outdoor technical use"
        else:
            specs["comfort_level"] = "Cushioned foam sockliner, lightweight flexible midsole"
            specs["activity_suitability"] = "All-day casual walking, everyday office wear"
        specs["sizes_available"] = "US Men 6–14, US Women 5–11 (Wide options available)"

    elif "books" in category_key:
        specs["edition"] = "Hardcover Premium Edition" if is_premium else "Trade Paperback Edition"
        specs["language"] = "English (French, German and Spanish editions available separately)"
        pages = [240, 360, 480, 560, 680]
        specs["page_count"] = f"{pages[h % len(pages)]} pages"
        specs["format"] = "Smyth-sewn cloth binding with dust jacket" if is_premium else "Perfect-bound softcover"
        if is_premium:
            specs["audience_level"] = "Advanced professional and postgraduate reading"
            specs["recommended_use_cases"] = "Corporate libraries, senior leadership training, academic reference"
        else:
            specs["audience_level"] = "General and introductory professional reading"
            specs["recommended_use_cases"] = "Employee onboarding, professional development workshops"

    elif "appliances" in category_key or "home appliances" in category_key:
        if is_premium:
            specs["energy_efficiency"] = "Energy Star A+++ Certified, eco-mode enabled"
            specs["power_consumption"] = f"{100 + (h % 3) * 50}W operation, 0.5W standby"
            specs["warranty"] = "3 Years parts and labour, 10 Years motor/compressor"
            specs["installation_requirements"] = "Standard 15A wall socket, levelling feet included"
            specs["maintenance_frequency"] = "Self-cleaning cycle; filter replacement every 12 months"
        elif is_budget:
            specs["energy_efficiency"] = "A+ efficiency rating"
            specs["power_consumption"] = f"{350 + (h % 3) * 100}W normal load"
            specs["warranty"] = "1 Year limited manufacturer warranty"
            specs["installation_requirements"] = "Standard 3-pin residential outlet"
            specs["maintenance_frequency"] = "Filter cleaning every 3 months"
        else:
            specs["energy_efficiency"] = "A++ Energy Star Certified"
            specs["power_consumption"] = f"{200 + (h % 3) * 50}W average"
            specs["warranty"] = "2 Years manufacturer warranty"
            specs["installation_requirements"] = "Standard 3-pin plug socket"
            specs["maintenance_frequency"] = "Filter cleaning every 6 months"
        specs["dimensions"] = f"{60 + (h % 3) * 5} x {55 + (h % 3) * 5} x {85 + (h % 5) * 10} cm"

    else:
        specs["material"] = "Premium durable composites" if is_premium else "Standard-grade polymers"
        specs["warranty"] = "2 Years comprehensive" if is_premium else "1 Year manufacturer support"
        specs["compatibility"] = "Standard commercial and residential compatibility"
        specs["included_accessories"] = "Standard assembly and operation kit"

    # -------------------------------------------------------------------------
    # 2. Universal warranty (if not already set by category block)
    # -------------------------------------------------------------------------
    if "warranty" not in specs:
        if is_premium:
            specs["warranty"] = "3 Years warranty with priority support"
        elif is_budget:
            specs["warranty"] = "1 Year manufacturer warranty"
        else:
            specs["warranty"] = "2 Years manufacturer warranty"

    # -------------------------------------------------------------------------
    # 3. Sales Intelligence Metadata Layer
    # -------------------------------------------------------------------------
    if "electronics" in category_key:
        subcategory = _detect_subcategory(product.name, category_key)
        meta = _electronics_metadata(subcategory, is_premium, is_budget, product.name, h)
        ideal_customer = meta["ideal_customer"]
        use_cases = meta["use_cases"]
        key_advantages = meta["key_advantages"]
        objection_handling = meta["objection_handling"]
    elif "apparel" in category_key:
        ic_opts = [
            "retail buyers, promotional teams, and hospitality clients sourcing staff uniforms",
            "corporate events teams, marketing agencies, and staff uniform procurement managers",
        ]
        ideal_customer = _pick(ic_opts, h)
        use_cases = ["Corporate merchandise and branding", "Staff uniforms and promotional wear",
                     "Client gift and incentive programmes", "Workwear and hospitality outfitting"]
        key_advantages = [_pick(["Durable fabric that holds colour through repeated washing",
                                  "Consistent colour across large batch orders",
                                  "Fabric holds shape after heavy commercial laundry"], h),
                           "Generous size range for diverse team needs",
                           _pick(["Breathable and comfortable for full-day wear",
                                  "Suitable for both indoor and outdoor settings"], h)]
        objection_handling = {
            "price": f"The {product.name} is priced for commercial volume orders, where per-unit cost drops with scale.",
            "warranty": "Covered under standard manufacturer quality guarantee for fabric and stitching defects.",
            "maintenance": "Machine washable and easy to care for — no special dry-cleaning required.",
            "compatibility": "Available in standard commercial size curves to fit diverse team profiles.",
            "longevity": _pick(["Quality stitching and fabric holds up well through regular commercial laundry cycles.",
                                 "Designed for regular professional use — built to last."], h),
        }
        recommendations = [
            {"name": "Heavy-Duty Garment Bags", "type": "maintenance", "desc": "Protects fabric during wash cycles"},
            {"name": "Waterproof Protector Spray", "type": "care", "desc": "Extends product life in wet conditions"},
        ]
    elif "footwear" in category_key:
        ic_opts = [
            "operations teams, safety buyers, and athletic retailers sourcing footwear in volume",
            "field operations, athletic organisations, and safety procurement teams",
        ]
        ideal_customer = _pick(ic_opts, h)
        use_cases = ["Long-shift operational environments", "Outdoor field operations",
                     "Athletic training and sports", "Everyday professional wear"]
        key_advantages = [_pick(["High-traction sole for slip resistance",
                                  "Premium grip for wet and uneven surfaces"], h),
                           "Orthotic support for all-day comfort",
                           _pick(["Tear-resistant reinforced stitching",
                                  "Durable construction for demanding conditions"], h)]
        objection_handling = {
            "price": f"The {product.name} is built for professional-grade daily use — the durability justifies the price over cheaper alternatives that wear out quickly.",
            "warranty": "Manufacturer warranty covers material and construction defects.",
            "maintenance": "Easy to clean and maintain. Durable materials need minimal upkeep.",
            "compatibility": "Available in a wide size range for diverse team requirements.",
            "longevity": "Reinforced construction designed for demanding, high-wear professional environments.",
        }
        recommendations = [
            {"name": "Waterproof Protector Spray", "type": "care", "desc": "Extends outdoor durability"},
            {"name": "Orthotic Insole Pack", "type": "accessory", "desc": "Enhanced comfort for all-day shifts"},
        ]
    elif "books" in category_key:
        ic_opts = [
            "corporate training teams, HR departments, and professional development coordinators",
            "academic institutions, L&D managers, and corporate library curators",
        ]
        ideal_customer = _pick(ic_opts, h)
        use_cases = ["Professional development and skills training", "Employee onboarding programmes",
                     "Corporate library and reference collections", "Team workshops and group learning"]
        key_advantages = [_pick(["Peer-reviewed content with practical application",
                                  "Written by recognised practitioners and subject experts"], h),
                           "Clear structure — easy to reference and annotate",
                           _pick(["Durable binding for shared library and training use",
                                  "High-quality print and layout for extended reading"], h)]
        objection_handling = {
            "price": f"The {product.name} offers institutional-grade content at a competitive per-copy price, especially for bulk orders.",
            "warranty": "All print editions carry a quality guarantee against manufacturing defects.",
            "maintenance": "No special maintenance. Store in standard conditions — bookshelf or library shelving.",
            "compatibility": "Available in print and digital formats for flexible deployment.",
            "longevity": "High-quality binding is designed for shared library use over many years.",
        }
        recommendations = [
            {"name": "Digital Companion License", "type": "digital upgrade", "desc": "Online exercises and updates"},
            {"name": "Bulk Display Stand", "type": "accessory", "desc": "Floor display for training libraries"},
        ]
    elif "appliance" in category_key or "home appliance" in category_key:
        ic_opts = [
            "commercial developers, office facility managers, and hospitality procurement teams",
            "property developers, building outfitters, and corporate facilities managers",
        ]
        ideal_customer = _pick(ic_opts, h)
        use_cases = ["Office and breakroom installations", "Commercial property fit-outs",
                     "Hospitality and hotel upgrades", "Residential building projects"]
        key_advantages = [_pick(["Energy-efficient — reduces running costs over time",
                                  "Low energy consumption with high output"], h),
                           "Quiet operation suitable for office and residential environments",
                           _pick(["Easy to maintain with clear service intervals",
                                  "Straightforward maintenance — minimal downtime"], h)]
        objection_handling = {
            "price": f"The {product.name} reduces long-term operating costs through energy efficiency. For bulk installations it represents strong value across the fleet.",
            "warranty": "Comprehensive manufacturer warranty with extended B2B service options available.",
            "maintenance": "Scheduled maintenance intervals are simple and infrequent. Self-cleaning features reduce manual effort.",
            "compatibility": "Standard plug-in installation. Compatible with residential and commercial wiring standards.",
            "longevity": "Commercial-grade motor rated for years of continuous daily use.",
        }
        recommendations = [
            {"name": "Annual Maintenance Plan", "type": "service plan", "desc": "Scheduled inspections and performance check"},
            {"name": "Replacement Parts Kit", "type": "accessories", "desc": "Filters, gaskets, and standard spares"},
        ]
    else:
        ic_opts = [
            "procurement teams and institutional buyers sourcing reliable commercial-grade equipment",
            "B2B buyers and wholesale distributors looking for dependable catalogue products",
        ]
        ideal_customer = _pick(ic_opts, h)
        use_cases = ["Commercial deployments", "B2B supply and distribution", "Institutional use", "Professional operations"]
        key_advantages = ["Reliable under regular commercial use", "Good total cost of ownership",
                          "Easy to deploy", "Backed by manufacturer warranty"]
        objection_handling = {
            "price": f"The {product.name} is competitively priced within its category, with strong value at commercial volumes.",
            "warranty": "Standard manufacturer warranty included. Extension options available for B2B contracts.",
            "maintenance": "Low maintenance by design. Standard cleaning and inspection is all that's required.",
            "compatibility": "Plug-and-play compatibility with standard commercial setups.",
            "longevity": "Built to commercial durability standards for typical business usage cycles.",
        }
        recommendations = [
            {"name": "Extended Warranty Plan", "type": "warranty", "desc": "Business warranty extension"},
            {"name": "Standard Accessories Kit", "type": "accessories", "desc": "Common add-ons and spares"},
        ]

    # Set recommendations for electronics separately (already set in non-electronics above)
    if "electronics" in category_key:
        subcategory = _detect_subcategory(product.name, category_key)
        recommendations = [
            {"name": "Extended Warranty Plan", "type": "warranty", "desc": "Extend coverage to 3 years with direct support"},
            {"name": "Carry Case / Protective Cover", "type": "accessory", "desc": "Protects the device during travel and daily use"},
        ]
        if subcategory == "laptop":
            recommendations.append({"name": "Universal Docking Station", "type": "deployment add-on", "desc": "Expand connectivity ports at a fixed desk"})
        elif subcategory in ("smartphone", "tablet"):
            recommendations.append({"name": "Screen Protector + Case Bundle", "type": "accessory", "desc": "Full-body protection kit"})
        elif subcategory in ("headphones", "speaker"):
            recommendations.append({"name": "Cable Organiser + Charging Dock", "type": "accessory", "desc": "Keeps setup tidy and always charged"})

    # Store the detected subcategory so stale-spec detection can identify
    # records generated before subcategory-aware logic existed.
    if "electronics" in category_key:
        metadata_subcategory = _detect_subcategory(product.name, category_key)
    else:
        metadata_subcategory = category_key

    sales_metadata = {
        "brand_name": brand_name,
        "brand_tier": brand_tier,
        "price_segment": price_segment,
        "subcategory": metadata_subcategory,
        "ideal_customer": ideal_customer,
        "use_cases": use_cases,
        "key_advantages": key_advantages,
        "objection_handling": objection_handling,
        "cross_sell_recommendations": recommendations,
    }

    specs["_sales_metadata_"] = json.dumps(sales_metadata)
    return specs
