import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    OUTSCRAPER_API_KEY: str = os.getenv("OUTSCRAPER_API_KEY", "")
    SECRET_KEY: str = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI: str = os.getenv("DATABASE_URL", "sqlite:///whpc.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    REFRESH_INTERVAL_HOURS: int = int(os.getenv("REFRESH_INTERVAL_HOURS", "24"))
    DEBUG: bool = os.getenv("DEBUG", "0") == "1"


# ── Scrape targets ────────────────────────────────────────────────────────────
# Each entry describes one retailer / brand to scrape.
# `search_url` is the category/search page Crawl4AI will start from.
# `product_css` is the CSS selector for individual product cards on that page.
SCRAPE_TARGETS = [
    {
        "retailer": "CVS",
        "search_url": "https://www.cvs.com/search?searchTerm=women+health+test",
        "product_css": ".product-card",
        "logo": "https://www.cvs.com/favicon.ico",
    },
    {
        "retailer": "Walgreens",
        "search_url": "https://www.walgreens.com/search/results.jsp?Ntt=women+health+test",
        "product_css": ".product-tile",
        "logo": "https://www.walgreens.com/favicon.ico",
    },
    {
        "retailer": "Amazon",
        "search_url": "https://www.amazon.com/s?k=women+at+home+health+test",
        "product_css": '[data-component-type="s-search-result"]',
        "logo": "https://www.amazon.com/favicon.ico",
    },
    {
        "retailer": "Target",
        "search_url": "https://www.target.com/s?searchTerm=womens+health+test",
        "product_css": '[data-test="product-details"]',
        "logo": "https://www.target.com/favicon.ico",
    },
    {
        "retailer": "Everlywell",
        "search_url": "https://www.everlywell.com/collections/womens-health",
        "product_css": ".product-item",
        "logo": "https://www.everlywell.com/favicon.ico",
    },
    {
        "retailer": "LetsGetChecked",
        "search_url": "https://www.letsgetchecked.com/us/en/women/",
        "product_css": ".test-card",
        "logo": "https://www.letsgetchecked.com/favicon.ico",
    },
]

# ── Test categories ───────────────────────────────────────────────────────────
TEST_CATEGORIES = [
    "Pregnancy",
    "Ovulation & Fertility",
    "STI / STD",
    "Menopause & FSH",
    "Thyroid",
    "Hormone Panel",
    "UTI",
    "Vaginal Health",
    "PCOS",
    "Breast Cancer Risk",
    "General Wellness",
]
