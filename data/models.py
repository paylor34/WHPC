"""
SQLAlchemy models for the Women's Health Price Comparison directory.
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Product(db.Model):
    """A unique at-home women's health test product (brand + test name)."""
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    brand = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(120), nullable=False, index=True)
    description = db.Column(db.Text, default="")
    image_url = db.Column(db.String(512), default="")
    # Comma-separated tags, e.g. "FSH,estrogen,progesterone"
    tags = db.Column(db.String(512), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    listings = db.relationship(
        "Listing", back_populates="product", cascade="all, delete-orphan"
    )

    @property
    def lowest_price(self):
        active = [l for l in self.listings if l.in_stock]
        return min((l.price for l in active), default=None)

    @property
    def tag_list(self):
        return [t.strip() for t in self.tags.split(",") if t.strip()]

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "brand": self.brand,
            "category": self.category,
            "description": self.description,
            "image_url": self.image_url,
            "tags": self.tag_list,
            "lowest_price": self.lowest_price,
            "listings": [l.to_dict() for l in self.listings],
        }


class Listing(db.Model):
    """
    A specific price/availability record for a Product at one retailer.
    Multiple listings can exist per product (one per retailer).
    """
    __tablename__ = "listings"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    retailer = db.Column(db.String(120), nullable=False)
    retailer_logo = db.Column(db.String(512), default="")
    price = db.Column(db.Float, nullable=False)
    original_price = db.Column(db.Float, nullable=True)   # before discount
    currency = db.Column(db.String(8), default="USD")
    url = db.Column(db.String(1024), nullable=False)
    in_stock = db.Column(db.Boolean, default=True)
    # Source: 'crawl4ai' | 'outscraper' | 'manual'
    source = db.Column(db.String(32), default="crawl4ai")
    scraped_at = db.Column(db.DateTime, default=datetime.utcnow)

    product = db.relationship("Product", back_populates="listings")

    @property
    def discount_pct(self):
        if self.original_price and self.original_price > self.price:
            return round((1 - self.price / self.original_price) * 100)
        return None

    def to_dict(self):
        return {
            "id": self.id,
            "retailer": self.retailer,
            "retailer_logo": self.retailer_logo,
            "price": self.price,
            "original_price": self.original_price,
            "discount_pct": self.discount_pct,
            "currency": self.currency,
            "url": self.url,
            "in_stock": self.in_stock,
            "source": self.source,
            "scraped_at": self.scraped_at.isoformat(),
        }


class ScrapeLog(db.Model):
    """Audit trail for scrape runs."""
    __tablename__ = "scrape_logs"

    id = db.Column(db.Integer, primary_key=True)
    retailer = db.Column(db.String(120))
    source = db.Column(db.String(32))
    products_found = db.Column(db.Integer, default=0)
    products_updated = db.Column(db.Integer, default=0)
    errors = db.Column(db.Text, default="")
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    finished_at = db.Column(db.DateTime, nullable=True)
    success = db.Column(db.Boolean, default=True)
