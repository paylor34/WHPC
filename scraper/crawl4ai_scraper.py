"""
Crawl4AI-based scraper for women's health at-home test products.

Crawl4AI works by:
  1. Launching a headless Playwright browser (handles JS-rendered pages)
  2. Extracting structured data via CSS selectors or an LLM extraction strategy
  3. Returning clean markdown + structured JSON you can immediately persist

Supported retailers: CVS, Walgreens, Amazon, Target, Everlywell, LetsGetChecked,
                     Labcorp On Demand, Quest Diagnostics
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
# Each schema has:
#   baseSelector — the repeating product card container
#   fields       — field-level CSS selectors within that container
#   wait_for     — selector Crawl4AI waits on before extracting (JS render guard)
#   base_url     — used to resolve relative hrefs
#
# Confidence legend in comments:  ✓ verified  ~ likely  ? guessed
# Run `python -m scraper.selector_inspector` locally to re-verify.

CVS_SCHEMA = {
    # CVS is a React SPA; products render inside a list with class
    # "product-list" and individual cards are "product-list-item".
    # data-testid attributes are more stable than plain class names.
    # ~ based on publicly documented CVS React DOM patterns.
    "name": "CVS Products",
    "baseSelector": ".product-list-item",          # ~ also try [data-testid="product-card"]
    "wait_for": ".product-list-item",
    "base_url": "https://www.cvs.com",
    "fields": [
        # ~ product name is usually inside a heading or data-testid="product-title"
        {"name": "name",           "selector": "[data-testid='product-title'], .product-name, h3",
                                   "type": "text"},
        # ~ price appears as <span class="price"> or inside a promo wrapper
        {"name": "price",          "selector": "[data-testid='price-display'], .price, [class*='price']",
                                   "type": "text"},
        # ~ strike-through shown only when on sale
        {"name": "original_price", "selector": "[class*='strike'], [class*='was-price'], del, s",
                                   "type": "text"},
        # ~ product link wraps the image/name
        {"name": "url",            "selector": "a[href*='/shop/']",
                                   "type": "attribute", "attribute": "href"},
        # Crawl4AI uses Playwright so images are rendered; src is populated after scroll.
        # data-src is a fallback for sites using IntersectionObserver without swap.
        {"name": "image_url",      "selector": "picture img, img[class*='product'], img",
                                   "type": "attribute", "attribute": "src"},
        # ~ add-to-cart present when in stock
        {"name": "in_stock",       "selector": "[data-testid='add-to-cart'], button[class*='add-to-cart']",
                                   "type": "exists"},
    ],
}

WALGREENS_SCHEMA = {
    # Walgreens renders product tiles server-side for the first page;
    # subsequent pages are client-side via their WAG React shell.
    # ~ based on Walgreens search page DOM analysis reports (2023-24).
    "name": "Walgreens Products",
    "baseSelector": ".product-tile",               # ~ also try [class*='productTile']
    "wait_for": ".product-tile",
    "base_url": "https://www.walgreens.com",
    "fields": [
        # ~ name in <p> or <a> with class "product-name"
        {"name": "name",           "selector": ".product-name a, .product-tile-name, [class*='product-name']",
                                   "type": "text"},
        # ~ regular price in span; promo price may override
        {"name": "price",          "selector": ".regular-price, .product-price, [class*='sale-price'], [class*='price']",
                                   "type": "text"},
        # ~ was-price only present during promotions
        {"name": "original_price", "selector": "[class*='was-price'], [class*='strikethrough'], del",
                                   "type": "text"},
        # ~ link wraps the tile or is on the product name anchor
        {"name": "url",            "selector": "a.product-tile-link, a[href*='/store/']",
                                   "type": "attribute", "attribute": "href"},
        {"name": "image_url",      "selector": "img.product-image, picture img, img",
                                   "type": "attribute", "attribute": "src"},
        # ~ in-stock if add-to-cart button is present and not disabled
        {"name": "in_stock",       "selector": ".add-to-cart-btn:not([disabled]), [class*='addToCart']:not([disabled])",
                                   "type": "exists"},
    ],
}

AMAZON_SCHEMA = {
    # Amazon's search result structure is well-documented and rarely changes
    # at the attribute level (data-component-type, .a-price, .s-image).
    # ✓ high confidence — corroborated by multiple open-source scrapers.
    "name": "Amazon Products",
    "baseSelector": '[data-component-type="s-search-result"]',   # ✓
    "wait_for": '[data-component-type="s-search-result"]',
    "base_url": "https://www.amazon.com",
    "fields": [
        # ✓ title is always in h2 > span with this class
        {"name": "name",           "selector": "h2 span.a-text-normal, h2 .a-size-base-plus, h2 span",
                                   "type": "text"},
        # ✓ .a-offscreen holds the screen-reader price string e.g. "$12.99"
        # data-a-size="xl" targets the main price, not the cents-only span
        {"name": "price",          "selector": ".a-price[data-a-size='xl'] .a-offscreen, .a-price .a-offscreen",
                                   "type": "text"},
        # ✓ strike-through price uses data-a-strike attribute
        {"name": "original_price", "selector": ".a-price[data-a-strike='true'] .a-offscreen, span.a-price.a-text-price .a-offscreen",
                                   "type": "text"},
        # ✓ product URL on the h2 anchor; returns a relative /dp/... path
        {"name": "url",            "selector": "h2 a.a-link-normal, a.s-no-outline",
                                   "type": "attribute", "attribute": "href"},
        # ✓ product image always has class s-image
        {"name": "image_url",      "selector": "img.s-image",
                                   "type": "attribute", "attribute": "src"},
        # ✓ star rating text for future use
        {"name": "rating",         "selector": "span.a-icon-alt",
                                   "type": "text"},
        # ~ add-to-cart is not always present on search results; price
        # existing is a better in-stock signal — handled in _normalize()
        {"name": "in_stock",       "selector": ".a-declarative[data-action='add-to-cart'], input[name='add-to-cart']",
                                   "type": "exists"},
    ],
}

TARGET_SCHEMA = {
    # Target uses data-test attributes extensively and keeps them stable
    # across React re-renders — the most reliable selectors of any retailer here.
    # ✓ high confidence — data-test= values are part of Target's QA harness.
    "name": "Target Products",
    "baseSelector": '[data-test="product-list-item"]',            # ✓ outer wrapper
    "wait_for": '[data-test="product-list-item"]',
    "base_url": "https://www.target.com",
    "fields": [
        # ✓ product title anchor — doubles as the link
        {"name": "name",           "selector": '[data-test="product-title"]',
                                   "type": "text"},
        # ✓ current/sale price; the span inside holds the formatted value
        {"name": "price",          "selector": '[data-test="current-price"] span, [data-test="current-price"]',
                                   "type": "text"},
        # ✓ regular price shown alongside when on sale
        {"name": "original_price", "selector": '[data-test="reg-price"] span, [data-test="regular-price"]',
                                   "type": "text"},
        # ✓ href on the product title anchor
        {"name": "url",            "selector": '[data-test="product-title"]',
                                   "type": "attribute", "attribute": "href"},
        # ~ product image; Target uses srcset so grab the src fallback
        {"name": "image_url",      "selector": '[data-test="product-image"] img, picture img',
                                   "type": "attribute", "attribute": "src"},
        # ~ shipping/pickup block present when in stock
        {"name": "in_stock",       "selector": '[data-test="shippingBlock"], button[data-test="addToCartButton"]',
                                   "type": "exists"},
    ],
}

EVERLYWELL_SCHEMA = {
    # Everlywell uses Shopify (Debut-derived theme) with some custom CSS.
    # Collections page renders product cards as <li class="product-item">.
    # ~ based on Shopify Debut theme DOM patterns + Everlywell-specific overrides.
    "name": "Everlywell Products",
    "baseSelector": "li.product-item, .product-item",             # ~ Shopify Debut
    "wait_for": ".product-item",
    "base_url": "https://www.everlywell.com",
    "fields": [
        # ~ title in <a> or <h3> with BEM class
        {"name": "name",           "selector": ".product-item__title, .product-item__title a, h3[class*='title']",
                                   "type": "text"},
        # ~ Shopify price structure: .price > .price__regular > .price-item--regular
        {"name": "price",          "selector": ".price-item--regular, .price .money, [class*='price'] .money",
                                   "type": "text"},
        # ~ compare-at price (Shopify's term for was-price)
        {"name": "original_price", "selector": ".price__compare .price-item, .price--compare .money",
                                   "type": "text"},
        # ~ product link — Shopify always uses /products/<handle>
        {"name": "url",            "selector": "a.product-item__link, a[href*='/products/']",
                                   "type": "attribute", "attribute": "href"},
        {"name": "image_url",      "selector": ".product-item__image, .card__media img, picture img",
                                   "type": "attribute", "attribute": "src"},
    ],
}

LGCHECKED_SCHEMA = {
    # LetsGetChecked has migrated to a Next.js app (2023+).
    # Their product cards no longer use classic BEM; they now use
    # utility/generated class names or semantic HTML with data- attributes.
    # ? lower confidence — run selector_inspector.py to verify.
    "name": "LetsGetChecked Products",
    "baseSelector": "article, [class*='TestCard'], [class*='test-card'], .product-card",   # ? try all
    "wait_for": "article",
    "base_url": "https://www.letsgetchecked.com",
    "fields": [
        # ? title commonly in h2/h3 inside the card article
        {"name": "name",           "selector": "h2, h3, [class*='title'], [class*='name']",
                                   "type": "text"},
        # ? price may be in a <span> or <p> with class containing "price"
        {"name": "price",          "selector": "[class*='price'], [data-testid*='price']",
                                   "type": "text"},
        # ? internal links follow /us/en/... or /test/... pattern
        {"name": "url",            "selector": "a[href*='/test/'], a[href*='/en/'], article > a, a",
                                   "type": "attribute", "attribute": "href"},
        # ? images are usually the first <img> or <picture img> in the card
        {"name": "image_url",      "selector": "picture img, img[src*='cdn'], img",
                                   "type": "attribute", "attribute": "src"},
    ],
}

LABCORP_SCHEMA = {
    # Labcorp On Demand is a React-based direct-to-consumer lab-test storefront.
    # Products are rendered as test cards on their category/search pages.
    # ? lower confidence — run selector_inspector.py to verify against live DOM.
    "name": "Labcorp On Demand Products",
    "baseSelector": ".test-card, [class*='TestCard'], [class*='test-card'], article",  # ?
    "wait_for": ".test-card, article",
    "base_url": "https://www.labcorpondemand.com",
    "fields": [
        # ? title in h2/h3 or a heading within the card
        {"name": "name",           "selector": "h2, h3, [class*='title'], [class*='name']",
                                   "type": "text"},
        # ? price in a <span> or <p> containing "price" in the class
        {"name": "price",          "selector": "[class*='price'], [data-testid*='price']",
                                   "type": "text"},
        # ? original price if shown (sale/discount)
        {"name": "original_price", "selector": "[class*='original-price'], [class*='was-price'], del, s",
                                   "type": "text"},
        # ? product link — Labcorp uses /lab-tests/<slug> paths
        {"name": "url",            "selector": "a[href*='/lab-tests/'], a[href*='/test/'], article > a, a",
                                   "type": "attribute", "attribute": "href"},
        # ? first image inside the card
        {"name": "image_url",      "selector": "picture img, img[src*='cdn'], img",
                                   "type": "attribute", "attribute": "src"},
        # ? add-to-cart / order button signals availability
        {"name": "in_stock",       "selector": "button[class*='add'], button[class*='order'], button[class*='cart']",
                                   "type": "exists"},
    ],
}

QUEST_SCHEMA = {
    # Quest Diagnostics QuestDirect is the direct-to-consumer portal for ordering
    # lab tests online without a doctor's order.  The site is a React SPA.
    # ? lower confidence — run selector_inspector.py to verify against live DOM.
    "name": "Quest Diagnostics Products",
    "baseSelector": ".product-card, [class*='ProductCard'], [class*='product-card'], article",  # ?
    "wait_for": ".product-card, article",
    "base_url": "https://questdirect.questdiagnostics.com",
    "fields": [
        # ? title in heading or dedicated class
        {"name": "name",           "selector": "h2, h3, [class*='title'], [class*='name']",
                                   "type": "text"},
        # ? price element
        {"name": "price",          "selector": "[class*='price'], [data-testid*='price']",
                                   "type": "text"},
        # ? compare-at / was price
        {"name": "original_price", "selector": "[class*='original-price'], [class*='compare'], del, s",
                                   "type": "text"},
        # ? product links follow /products/<slug> or /test/<slug>
        {"name": "url",            "selector": "a[href*='/products/'], a[href*='/test/'], article > a, a",
                                   "type": "attribute", "attribute": "href"},
        # ? product image
        {"name": "image_url",      "selector": "picture img, img[src*='cdn'], img",
                                   "type": "attribute", "attribute": "src"},
        # ? order button when available
        {"name": "in_stock",       "selector": "button[class*='order'], button[class*='add'], button[class*='cart']",
                                   "type": "exists"},
    ],
}

RETAILER_SCHEMAS = {
    "CVS": CVS_SCHEMA,
    "Walgreens": WALGREENS_SCHEMA,
    "Amazon": AMAZON_SCHEMA,
    "Target": TARGET_SCHEMA,
    "Everlywell": EVERLYWELL_SCHEMA,
    "LetsGetChecked": LGCHECKED_SCHEMA,
    "Labcorp On Demand": LABCORP_SCHEMA,
    "Quest Diagnostics": QUEST_SCHEMA,
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
    brand_sites = {"Everlywell", "LetsGetChecked", "Labcorp On Demand", "Quest Diagnostics"}
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


def _normalize(raw_item: dict, retailer: str, retailer_logo: str, base_url: str, schema: dict | None = None) -> Optional[ScrapedProduct]:
    """Convert a raw CSS-extracted dict into a ScrapedProduct."""
    name = (raw_item.get("name") or "").strip()
    price_raw = raw_item.get("price") or ""
    price = _parse_price(price_raw)

    if not name or price is None:
        return None

    # Resolve the product URL.
    # Use the schema's declared base_url (e.g. "https://www.amazon.com") so
    # that relative paths like "/dp/B000052XCW" become absolute correctly,
    # rather than being joined onto the search-result query URL.
    url = raw_item.get("url") or ""
    if url and not url.startswith("http"):
        declared_base = (schema or {}).get("base_url", "").rstrip("/")
        fallback_base = base_url.rstrip("/")
        root = declared_base or fallback_base
        url = root + "/" + url.lstrip("/")

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

    # Use the per-schema wait_for if available; fall back to baseSelector
    wait_for_sel = (schema or {}).get("wait_for") or (schema or {}).get("baseSelector") or "body"

    config = CrawlerRunConfig(
        extraction_strategy=strategy,
        # Block images/fonts to speed up the crawl (we get image URLs from HTML)
        # Scroll once to trigger lazy-load, wait for network to settle
        wait_for=wait_for_sel,
        js_code=(
            "window.scrollTo(0, document.body.scrollHeight);"
            "await new Promise(r => setTimeout(r, 1500));"
            "window.scrollTo(0, 0);"
        ),
        delay_before_return_html=2.5,
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
        p = _normalize(item, retailer, retailer_logo, search_url, schema=schema)
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
