"""
Export scraped product data from the SQLite DB to flat files.

Outputs (written to data/exports/):
  products.json   — one JSON object per product, listings nested inside
  listings.csv    — flat CSV, one row per listing (good for spreadsheets)

Usage:
  python run.py export
"""
from __future__ import annotations

import csv
import json
import os
from datetime import datetime

EXPORTS_DIR = os.path.join(os.path.dirname(__file__), "exports")


def export_all() -> tuple[int, int]:
    """
    Dump the full products + listings tables to data/exports/.

    Returns:
        (product_count, listing_count) — rows written to each file.
    """
    from data.models import Product

    os.makedirs(EXPORTS_DIR, exist_ok=True)

    products = Product.query.order_by(Product.category, Product.name).all()

    product_count = _write_json(products)
    listing_count = _write_csv(products)

    return product_count, listing_count


def _write_json(products) -> int:
    """Write products.json — full nested structure."""
    path = os.path.join(EXPORTS_DIR, "products.json")
    data = {
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "product_count": len(products),
        "products": [p.to_dict() for p in products],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return len(products)


def _write_csv(products) -> int:
    """Write listings.csv — flat table, one row per retailer listing."""
    path = os.path.join(EXPORTS_DIR, "listings.csv")
    fieldnames = [
        "product_id",
        "product_name",
        "brand",
        "category",
        "tags",
        "retailer",
        "price",
        "original_price",
        "discount_pct",
        "currency",
        "in_stock",
        "url",
        "source",
        "scraped_at",
    ]

    listing_count = 0
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for product in products:
            for listing in product.listings:
                writer.writerow({
                    "product_id":     product.id,
                    "product_name":   product.name,
                    "brand":          product.brand,
                    "category":       product.category,
                    "tags":           ",".join(product.tag_list),
                    "retailer":       listing.retailer,
                    "price":          listing.price,
                    "original_price": listing.original_price or "",
                    "discount_pct":   listing.discount_pct or "",
                    "currency":       listing.currency,
                    "in_stock":       listing.in_stock,
                    "url":            listing.url,
                    "source":         listing.source,
                    "scraped_at":     listing.scraped_at.isoformat(),
                })
                listing_count += 1

    return listing_count
