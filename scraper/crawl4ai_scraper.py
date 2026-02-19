"""
Crawl4AI-based scraper for women's health at-home test products.

Crawl4AI works by:
  1. Launching a headless Playwright browser (handles JS-rendered pages)
  2. Extracting structured data via CSS selectors or an LLM extraction strategy
  3. Returning clean markdown + structured JSON you can immediately persist

Supported retailers: CVS, Walgreens, Amazon, Target, Everlywell, LetsGetChecked
"""
import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from rich import print as rprint

# crawl4ai is imported lazily so the rest of the app works without it installed
try:
    from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
    from crawl4ai.extraction_strategy import JsonCssExtractionStrategy, LLMExtractionStrategy
    CRAWL4AI_AVAILABLE = True
except ImportError:
    CRAWL4AI_AVAILABLE = False


@dataclass
class ScrapedProduct:
    """Intermediate data class — converted to DB models by the importer."""
    name: str
    brand: str
    price: float
    url: str
    retailer: str
    retailer_logo: str = ""
    original_price: Optional[float] = None
    image_url: str = ""
    description: str = ""
    category: str = "General Wellness"
    in_stock: bool = True
    tags: list[str] = field(default_factory=list)
    scraped_at: datetime = field(default_factory=datetime.utcnow)


# ── Per-retailer CSS extraction schemas ───────────────────────────────────────
# These tell Crawl4AI exactly which CSS selectors map to which fields.
# Adjust selectors when a retailer redesigns its pages.

CVS_SCHEMA = {
    "name": "CVS Products",
    "baseSelector": ".product-card",
    "fields": [
        {"name": "name",          "selector": ".product-title",      "type": "text"},
        {"name": "price",         "selector": ".price .value",       "type": "text"},
        {"name": "original_price","selector": ".price .strike",      "type": "text"},
        {"name": "url",           "selector": "a.product-link",      "type": "attribute", "attribute": "href"},
        {"name": "image_url",     "selector": "img.product-image",   "type": "attribute", "attribute": "src"},
        {"name": "in_stock",      "selector": ".add-to-cart",        "type": "exists"},
    ],
}

WALGREENS_SCHEMA = {
    "name": "Walgreens Products",
    "baseSelector": ".product-tile",
    "fields": [
        {"name": "name",          "selector": ".product-name",       "type": "text"},
        {"name": "price",         "selector": ".product-price",      "type": "text"},
        {"name": "url",           "selector": "a.product-tile-link", "type": "attribute", "attribute": "href"},
        {"name": "image_url",     "selector": "img.product-image",   "type": "attribute", "attribute": "src"},
        {"name": "in_stock",      "selector": ".add-to-cart-btn",    "type": "exists"},
    ],
}

AMAZON_SCHEMA = {
    "name": "Amazon Products",
    "baseSelector": '[data-component-type="s-search-result"]',
    "fields": [
        {"name": "name",      "selector": "h2 span",                              "type": "text"},
        {"name": "price",     "selector": ".a-price .a-offscreen",                "type": "text"},
        {"name": "url",       "selector": "h2 a",                                 "type": "attribute", "attribute": "href"},
        {"name": "image_url", "selector": ".s-image",                             "type": "attribute", "attribute": "src"},
        {"name": "rating",    "selector": ".a-icon-alt",                          "type": "text"},
        {"name": "in_stock",  "selector": '[data-cy="add-to-cart-button-announce"]',"type": "exists"},
    ],
}

TARGET_SCHEMA = {
    "name": "Target Products",
    "baseSelector": '[data-test="product-details"]',
    "fields": [
        {"name": "name",      "selector": '[data-test="product-title"]',          "type": "text"},
        {"name": "price",     "selector": '[data-test="current-price"] span',     "type": "text"},
        {"name": "url",       "selector": "a",                                    "type": "attribute", "attribute": "href"},
        {"name": "image_url", "selector": "img",                                  "type": "attribute", "attribute": "src"},
        {"name": "in_stock",  "selector": '[data-test="shippingBlock"]',          "type": "exists"},
    ],
}

EVERLYWELL_SCHEMA = {
    "name": "Everlywell Products",
    "baseSelector": ".product-item",
    "fields": [
        {"name": "name",      "selector": ".product-item__title",                 "type": "text"},
        {"name": "price",     "selector": ".price",                               "type": "text"},
        {"name": "url",       "selector": "a.product-item__link",                 "type": "attribute", "attribute": "href"},
        {"name": "image_url", "selector": "img.product-item__image",              "type": "attribute", "attribute": "src"},
    ],
}

LGCHECKED_SCHEMA = {
    "name": "LetsGetChecked Products",
    "baseSelector": ".test-card",
    "fields": [
        {"name": "name",      "selector": ".test-card__title",                    "type": "text"},
        {"name": "price",     "selector": ".test-card__price",                    "type": "text"},
        {"name": "url",       "selector": "a.test-card__link",                    "type": "attribute", "attribute": "href"},
        {"name": "image_url", "selector": "img",                                  "type": "attribute", "attribute": "src"},
    ],
}

RETAILER_SCHEMAS = {
    "CVS": CVS_SCHEMA,
    "Walgreens": WALGREENS_SCHEMA,
    "Amazon": AMAZON_SCHEMA,
    "Target": TARGET_SCHEMA,
    "Everlywell": EVERLYWELL_SCHEMA,
    "LetsGetChecked": LGCHECKED_SCHEMA,
}


def _parse_price(raw: str) -> Optional[float]:
    """Extract a float from strings like '$24.99', '24.99', '$24'."""
    if not raw:
        return None
    match = re.search(r"[\d,]+\.?\d*", raw.replace(",", ""))
    return float(match.group()) if match else None


def _infer_brand(name: str, retailer: str) -> str:
    """
    Simple heuristic: if the retailer is a direct brand site, use it.
    Otherwise try to detect brand prefix in the product name.
    """
    brand_sites = {"Everlywell", "LetsGetChecked"}
    if retailer in brand_sites:
        return retailer
    known_brands = [
        "Clearblue", "First Response", "Pregmate", "Easy@Home", "Proov",
        "Inito", "Mira", "Wisp", "Everlywell", "LetsGetChecked", "Nurx",
        "at&t", "Stix", "MomMed",
    ]
    for brand in known_brands:
        if brand.lower() in name.lower():
            return brand
    return retailer  # fallback


def _infer_category(name: str, description: str) -> str:
    text = (name + " " + description).lower()
    if any(k in text for k in ["pregnan", "pregnancy"]):
        return "Pregnancy"
    if any(k in text for k in ["ovulat", "fertility", "lh surge", "fsh"]):
        return "Ovulation & Fertility"
    if any(k in text for k in ["sti", "std", "chlamydia", "gonorrhea", "hiv", "herpes", "syphilis"]):
        return "STI / STD"
    if any(k in text for k in ["menopause", "perimenopause"]):
        return "Menopause & FSH"
    if any(k in text for k in ["thyroid", "tsh", "t3", "t4"]):
        return "Thyroid"
    if any(k in text for k in ["hormone", "estrogen", "progesterone", "testosterone", "cortisol"]):
        return "Hormone Panel"
    if any(k in text for k in ["uti", "urinary tract"]):
        return "UTI"
    if any(k in text for k in ["vaginal", "bv", "bacterial vaginosis", "yeast", "ph"]):
        return "Vaginal Health"
    if any(k in text for k in ["pcos", "polycystic"]):
        return "PCOS"
    if any(k in text for k in ["brca", "breast cancer", "genetic"]):
        return "Breast Cancer Risk"
    return "General Wellness"


def _normalize(raw_item: dict, retailer: str, retailer_logo: str, base_url: str) -> Optional[ScrapedProduct]:
    """Convert a raw CSS-extracted dict into a ScrapedProduct."""
    name = (raw_item.get("name") or "").strip()
    price_raw = raw_item.get("price") or ""
    price = _parse_price(price_raw)

    if not name or price is None:
        return None

    url = raw_item.get("url") or ""
    if url and not url.startswith("http"):
        url = base_url.rstrip("/") + "/" + url.lstrip("/")

    orig_raw = raw_item.get("original_price") or ""
    original_price = _parse_price(orig_raw)

    description = (raw_item.get("description") or "").strip()
    category = _infer_category(name, description)

    return ScrapedProduct(
        name=name,
        brand=_infer_brand(name, retailer),
        price=price,
        original_price=original_price,
        url=url,
        retailer=retailer,
        retailer_logo=retailer_logo,
        image_url=raw_item.get("image_url") or "",
        description=description,
        category=category,
        in_stock=bool(raw_item.get("in_stock", True)),
    )


# ── Main async scraper ─────────────────────────────────────────────────────────

async def scrape_retailer(
    retailer: str,
    search_url: str,
    retailer_logo: str = "",
    use_llm: bool = False,
    llm_provider: str = "openai/gpt-4o-mini",
    llm_api_key: str = "",
) -> list[ScrapedProduct]:
    """
    Scrape one retailer's search/category page and return a list of ScrapedProducts.

    Args:
        retailer: Human-readable retailer name (must match RETAILER_SCHEMAS key).
        search_url: The URL of the category/search results page to crawl.
        retailer_logo: URL to the retailer's favicon/logo.
        use_llm: If True, use LLM extraction instead of CSS selectors.
                 Slower but more robust against layout changes.
        llm_provider: e.g. "openai/gpt-4o-mini" (only used when use_llm=True).
        llm_api_key: API key for the LLM provider (only used when use_llm=True).

    Returns:
        List of ScrapedProduct instances.

    How it works:
        1. AsyncWebCrawler launches a headless Chromium browser via Playwright.
        2. It navigates to `search_url`, waits for JS to render, then extracts
           structured data using either a CSS schema or an LLM prompt.
        3. The raw dicts are normalised and returned as ScrapedProduct objects.
    """
    if not CRAWL4AI_AVAILABLE:
        raise RuntimeError(
            "crawl4ai is not installed. Run: pip install crawl4ai && playwright install"
        )

    schema = RETAILER_SCHEMAS.get(retailer)
    if schema is None and not use_llm:
        raise ValueError(
            f"No CSS schema for retailer '{retailer}'. "
            "Add one to RETAILER_SCHEMAS or pass use_llm=True."
        )

    # Choose extraction strategy
    if use_llm:
        instruction = (
            "Extract all women's health at-home test products from this page. "
            "For each product return: name, price (numeric USD), original_price (if discounted), "
            "url, image_url, description. Return as JSON array."
        )
        strategy = LLMExtractionStrategy(
            provider=llm_provider,
            api_token=llm_api_key,
            instruction=instruction,
        )
    else:
        strategy = JsonCssExtractionStrategy(schema, verbose=False)

    config = CrawlerRunConfig(
        extraction_strategy=strategy,
        # Wait for the product grid to appear before extracting
        wait_for=schema["baseSelector"] if schema else "body",
        # Scroll to load lazy-loaded products
        js_code="window.scrollTo(0, document.body.scrollHeight);",
        delay_before_return_html=2.0,
    )

    rprint(f"[cyan]Crawl4AI:[/cyan] scraping [bold]{retailer}[/bold] → {search_url}")

    async with AsyncWebCrawler(verbose=False) as crawler:
        result = await crawler.arun(url=search_url, config=config)

    if not result.success:
        rprint(f"[red]  ✗ failed:[/red] {result.error_message}")
        return []

    raw_items = json.loads(result.extracted_content or "[]")
    products = []
    for item in raw_items:
        p = _normalize(item, retailer, retailer_logo, search_url)
        if p:
            products.append(p)

    rprint(f"[green]  ✓[/green] {len(products)} products from {retailer}")
    return products


async def scrape_all(targets: list[dict], use_llm: bool = False, **llm_kwargs) -> list[ScrapedProduct]:
    """Scrape all configured targets concurrently."""
    tasks = [
        scrape_retailer(
            retailer=t["retailer"],
            search_url=t["search_url"],
            retailer_logo=t.get("logo", ""),
            use_llm=use_llm,
            **llm_kwargs,
        )
        for t in targets
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    all_products = []
    for r in results:
        if isinstance(r, Exception):
            rprint(f"[red]Scrape error:[/red] {r}")
        else:
            all_products.extend(r)
    return all_products
