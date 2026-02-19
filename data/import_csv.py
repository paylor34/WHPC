"""
Import scraped listings from data/exports/listings.csv into the database.

Upsert logic mirrors scraper/importer.py:
  - Products are matched by (name, brand); created if missing.
  - Listings are matched by (product_id, retailer); updated in-place.
"""
import csv
from datetime import datetime
from pathlib import Path

from data.models import db, Listing, Product, ScrapeLog

_CSV_PATH = Path(__file__).parent / "exports" / "listings.csv"


def import_from_csv(csv_path: Path | None = None) -> tuple[int, int]:
    """
    Read listings.csv and upsert Products + Listings into the DB.

    Returns:
        (products_created, listings_upserted)
    """
    path = csv_path or _CSV_PATH
    created = 0
    upserted = 0

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row["product_name"].strip()
            brand = (row.get("brand") or "Unknown").strip()
            category = (row.get("category") or "General Wellness").strip()
            tags = (row.get("tags") or "").strip()

            price_str = row.get("price", "").strip()
            if not price_str:
                continue  # skip rows with no price

            # ── Find or create Product ─────────────────────────────────────
            product = Product.query.filter_by(name=name, brand=brand).first()
            if not product:
                product = Product(
                    name=name,
                    brand=brand,
                    category=category,
                    tags=tags,
                )
                db.session.add(product)
                db.session.flush()  # get product.id before listing insert
                created += 1
            else:
                if tags and not product.tags:
                    product.tags = tags

            # ── Find or create Listing ─────────────────────────────────────
            retailer = (row.get("retailer") or "Unknown").strip()
            listing = Listing.query.filter_by(
                product_id=product.id, retailer=retailer
            ).first()
            if not listing:
                listing = Listing(product_id=product.id, retailer=retailer)
                db.session.add(listing)

            listing.price = float(price_str)
            orig = row.get("original_price", "").strip()
            listing.original_price = float(orig) if orig else None
            listing.currency = (row.get("currency") or "USD").strip()
            listing.url = row.get("url", "").strip()
            in_stock_raw = row.get("in_stock", "True").strip().lower()
            listing.in_stock = in_stock_raw in ("true", "1", "yes")
            listing.source = (row.get("source") or "csv").strip()
            listing.scraped_at = datetime.utcnow()
            upserted += 1

    db.session.commit()

    # Audit trail
    log = ScrapeLog(
        retailer="csv_import",
        source="csv",
        products_found=upserted,
        products_updated=upserted,
        started_at=datetime.utcnow(),
        finished_at=datetime.utcnow(),
        success=True,
    )
    db.session.add(log)
    db.session.commit()

    return created, upserted
