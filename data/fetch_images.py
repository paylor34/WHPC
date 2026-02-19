"""
Fetch and store product images from og:image meta tags on retailer pages.

Strategy:
  1. For each Product with no image_url, try its listing URLs one by one.
  2. Prefer Amazon listings (most reliable — og:image loads in static HTML).
  3. Fall back to other retailers until an image is found.
  4. Stores the discovered URL on Product.image_url and commits.

Usage (Flask CLI):
    flask fetch-images

Usage (from run.py):
    python run.py fetch-images
"""
import logging
import time
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

# Browser-like headers to avoid bot-detection blocks
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Retailer priority (lower = tried first). Amazon og:image works without JS.
_RETAILER_PRIORITY = {
    "amazon": 0,
    "walgreens": 1,
    "cvs": 2,
    "target": 3,
}


def _retailer_rank(listing) -> int:
    name = listing.retailer.lower()
    for key, rank in _RETAILER_PRIORITY.items():
        if key in name:
            return rank
    return 99


def _extract_og_image(html: str) -> str | None:
    """Return the og:image URL from raw HTML, or None if not found."""
    soup = BeautifulSoup(html, "lxml")
    for prop in ("og:image", "og:image:url", "twitter:image"):
        tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
        if tag:
            url = tag.get("content", "").strip()
            if url and url.startswith("http"):
                return url
    return None


def _fetch_image_for_product(product) -> str | None:
    """Try each listing URL (best retailer first) to find an og:image."""
    sorted_listings = sorted(product.listings, key=_retailer_rank)

    with httpx.Client(headers=_HEADERS, follow_redirects=True, timeout=12) as client:
        for listing in sorted_listings:
            url = listing.url
            try:
                log.info("  Trying %s (%s)…", listing.retailer, url[:60])
                resp = client.get(url)
                if resp.status_code == 200:
                    img = _extract_og_image(resp.text)
                    if img:
                        log.info("  ✓ Found image at %s", listing.retailer)
                        return img
                    log.info("  ✗ No og:image found at %s", listing.retailer)
                else:
                    log.info("  ✗ HTTP %s from %s", resp.status_code, listing.retailer)
            except Exception as exc:
                log.warning("  ✗ Error fetching %s: %s", listing.retailer, exc)

            time.sleep(0.6)  # gentle rate limit

    return None


def fetch_all_images(force: bool = False) -> tuple[int, int]:
    """
    Iterate over all Products and populate missing image_url fields.

    Args:
        force: If True, re-fetch even products that already have an image_url.

    Returns:
        (updated, skipped) counts.
    """
    from data.models import db, Product

    products = Product.query.all()
    updated = 0
    skipped = 0

    for product in products:
        if product.image_url and not force:
            skipped += 1
            continue

        log.info("Fetching image for: %s", product.name)
        img_url = _fetch_image_for_product(product)

        if img_url:
            product.image_url = img_url
            db.session.commit()
            updated += 1
            log.info("  Saved image for %s", product.name)
        else:
            log.warning("  No image found for %s", product.name)

    return updated, skipped
