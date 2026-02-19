"""
Outscraper integration for Women's Health Price Comparison.

Outscraper exposes two useful APIs here:
  1. Google Shopping — returns prices from Google's shopping graph across
     many retailers in one API call.  Great for products that block direct
     scraping (Amazon, Walmart).
  2. Google Search / Maps — for finding clinic/pharmacy locations or
     verifying brand legitimacy.

Docs: https://outscraper.com/google-shopping-results/

Setup:
    pip install outscraper
    export OUTSCRAPER_API_KEY=<your key>
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from rich import print as rprint

try:
    from outscraper import ApiClient as OutscraperApiClient
    OUTSCRAPER_AVAILABLE = True
except ImportError:
    OUTSCRAPER_AVAILABLE = False


# Reuse the same ScrapedProduct dataclass shape for consistency
@dataclass
class ScrapedProduct:
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


# ── Queries to fire at Google Shopping ───────────────────────────────────────
# Each maps a human label to a search query.  The API returns the top ~20
# Shopping results for each query, including retailer name, price, and URL.
SHOPPING_QUERIES: dict[str, str] = {
    "Pregnancy":           "women at home pregnancy test kit",
    "Ovulation & Fertility": "at home ovulation fertility test kit",
    "STI / STD":           "at home STI STD test women",
    "Menopause & FSH":     "at home menopause FSH test",
    "Thyroid":             "at home thyroid test women",
    "Hormone Panel":       "at home hormone panel test women",
    "UTI":                 "at home UTI test strips women",
    "Vaginal Health":      "at home vaginal pH yeast BV test women",
    "PCOS":                "at home PCOS hormone test kit women",
    "General Wellness":    "at home women health test kit",
}


def _parse_price(raw: str | float | None) -> Optional[float]:
    if isinstance(raw, (int, float)):
        return float(raw)
    if not raw:
        return None
    match = re.search(r"[\d,]+\.?\d*", str(raw).replace(",", ""))
    return float(match.group()) if match else None


def _infer_brand(item: dict) -> str:
    return (
        item.get("brand")
        or item.get("seller")
        or item.get("store")
        or "Unknown"
    )


def _build_product(item: dict, category: str) -> Optional[ScrapedProduct]:
    """
    Map a raw Outscraper Google Shopping result dict to ScrapedProduct.

    Key fields returned by Outscraper Google Shopping:
        title, price, old_price, currency, link, thumbnail, seller,
        store, rating, reviews_count, delivery
    """
    name = (item.get("title") or "").strip()
    price = _parse_price(item.get("price"))

    if not name or price is None:
        return None

    return ScrapedProduct(
        name=name,
        brand=_infer_brand(item),
        price=price,
        original_price=_parse_price(item.get("old_price")),
        url=item.get("link") or "",
        retailer=item.get("store") or item.get("seller") or "Google Shopping",
        retailer_logo="",
        image_url=item.get("thumbnail") or "",
        description=item.get("description") or "",
        category=category,
        in_stock=True,           # Shopping results are generally in-stock
        tags=[],
        scraped_at=datetime.utcnow(),
    )


class OutscraperShopping:
    """
    Thin wrapper around the Outscraper Google Shopping endpoint.

    Usage:
        client = OutscraperShopping(api_key="...")
        products = client.search_all_categories()

    How it works:
        The Outscraper Google Shopping API fires a Google Shopping search for
        each query string, parses the Shopping tab results (product name,
        price, retailer, URL, image), and returns them as structured JSON.
        We map those to ScrapedProduct and upsert them into the DB.

    Pricing / quota:
        Each query consumes Outscraper credits.  Batch mode (list of queries
        in one API call) is more efficient than individual calls.
    """

    def __init__(self, api_key: str):
        if not OUTSCRAPER_AVAILABLE:
            raise RuntimeError(
                "outscraper is not installed. Run: pip install outscraper"
            )
        if not api_key:
            raise ValueError("OUTSCRAPER_API_KEY must be set")
        self._client = OutscraperApiClient(api_key)

    def search_category(
        self,
        category: str,
        query: str,
        country: str = "us",
        language: str = "en",
        limit: int = 20,
    ) -> list[ScrapedProduct]:
        """
        Run one Google Shopping query and return ScrapedProducts.

        Args:
            category: Category label (e.g. "Pregnancy").
            query: Free-text shopping search string.
            country: Two-letter country code.
            language: Two-letter language code.
            limit: Max results to return per query.
        """
        rprint(f"[cyan]Outscraper:[/cyan] shopping → '{query}'")
        try:
            results = self._client.google_shopping(
                query,
                language=language,
                region=country,
                limit=limit,
            )
        except Exception as exc:
            rprint(f"[red]  ✗ Outscraper error:[/red] {exc}")
            return []

        # Outscraper returns a list-of-lists (one inner list per query)
        raw_items = results[0] if results else []
        products = []
        for item in raw_items:
            p = _build_product(item, category)
            if p:
                products.append(p)

        rprint(f"[green]  ✓[/green] {len(products)} products for '{category}'")
        return products

    def search_all_categories(
        self,
        queries: dict[str, str] | None = None,
        country: str = "us",
        limit: int = 20,
    ) -> list[ScrapedProduct]:
        """
        Run Shopping searches for every category in SHOPPING_QUERIES.

        Args:
            queries: Override the default SHOPPING_QUERIES dict.
            country: Two-letter country code.
            limit: Max results per category.

        Returns:
            Combined list of ScrapedProducts across all categories.
        """
        queries = queries or SHOPPING_QUERIES
        all_products: list[ScrapedProduct] = []
        for category, query in queries.items():
            products = self.search_category(category, query, country=country, limit=limit)
            all_products.extend(products)
        return all_products
