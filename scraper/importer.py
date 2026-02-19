"""
Imports ScrapedProduct objects (from crawl4ai or outscraper) into the DB.

Upsert logic:
  - Products are matched by (name, brand) — a new product row is only created
    if that combination doesn't already exist.
  - Listings are matched by (product_id, retailer) — one listing per
    product/retailer pair, updated in-place on re-scrape.
"""
from datetime import datetime
from typing import TYPE_CHECKING

from data.models import db, Listing, Product, ScrapeLog

if TYPE_CHECKING:
    from scraper.crawl4ai_scraper import ScrapedProduct


def upsert_products(
    scraped: list["ScrapedProduct"],
    source: str = "crawl4ai",
) -> tuple[int, int]:
    """
    Upsert a list of ScrapedProducts into the database.

    Returns:
        (products_created, listings_upserted) counts.
    """
    created = 0
    upserted = 0

    for sp in scraped:
        # ── Find or create the Product ────────────────────────────────────
        product = Product.query.filter_by(name=sp.name, brand=sp.brand).first()
        if not product:
            product = Product(
                name=sp.name,
                brand=sp.brand,
                category=sp.category,
                description=sp.description,
                image_url=sp.image_url,
                tags=",".join(sp.tags),
            )
            db.session.add(product)
            db.session.flush()   # get product.id before listing insert
            created += 1
        else:
            # Update mutable fields if we got better data
            if sp.description and not product.description:
                product.description = sp.description
            if sp.image_url and not product.image_url:
                product.image_url = sp.image_url

        # ── Find or create the Listing ────────────────────────────────────
        listing = Listing.query.filter_by(
            product_id=product.id, retailer=sp.retailer
        ).first()
        if not listing:
            listing = Listing(product_id=product.id, retailer=sp.retailer)
            db.session.add(listing)

        listing.price = sp.price
        listing.original_price = sp.original_price
        listing.url = sp.url
        listing.retailer_logo = sp.retailer_logo
        listing.image_url = sp.image_url if hasattr(sp, 'image_url') else ""
        listing.in_stock = sp.in_stock
        listing.source = source
        listing.scraped_at = datetime.utcnow()
        upserted += 1

    db.session.commit()
    return created, upserted


def log_scrape(
    retailer: str,
    source: str,
    products_found: int,
    products_updated: int,
    errors: str = "",
    success: bool = True,
) -> None:
    entry = ScrapeLog(
        retailer=retailer,
        source=source,
        products_found=products_found,
        products_updated=products_updated,
        errors=errors,
        started_at=datetime.utcnow(),
        finished_at=datetime.utcnow(),
        success=success,
    )
    db.session.add(entry)
    db.session.commit()
