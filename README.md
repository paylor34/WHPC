# Women's Health Price Comparison (WHPC)

A prototype price comparison directory for women's health at-home tests, built with Python + Flask, Crawl4AI, and Outscraper.

## Architecture

```
WHPC/
├── run.py                  Entry point (serve / seed / scrape)
├── config.py               Retailer targets, categories, env config
├── requirements.txt
├── .env.example
│
├── scraper/
│   ├── crawl4ai_scraper.py  Async JS-capable scraper (retailer product pages)
│   ├── outscraper_client.py Google Shopping via Outscraper API
│   └── importer.py          Upsert scraped data into the DB
│
├── data/
│   ├── models.py            SQLAlchemy models (Product, Listing, ScrapeLog)
│   └── seed.py              Realistic sample dataset (no API keys needed)
│
└── app/
    ├── routes.py            Flask blueprints (pages + JSON API)
    ├── templates/           Jinja2 HTML templates
    └── static/css/          Stylesheet
```

## How the scrapers work

### Crawl4AI (`scraper/crawl4ai_scraper.py`)

Crawl4AI launches a headless Playwright (Chromium) browser, navigates to a retailer's search/category page, waits for JavaScript to render, then extracts structured product data using CSS selectors defined per-retailer in `RETAILER_SCHEMAS`.

- **CSS strategy** — fast, deterministic, fragile to DOM changes
- **LLM strategy** — pass `use_llm=True`; Crawl4AI sends the page to an LLM (e.g. GPT-4o-mini) with a structured extraction prompt. Slower but robust to redesigns.

### Outscraper (`scraper/outscraper_client.py`)

Outscraper's Google Shopping API fires a shopping search query for each test category and returns structured results (name, price, retailer, URL, image) without you needing to scrape anything yourself. Ideal for retailers that heavily block crawlers (Amazon, Walmart).

## Quickstart

```bash
# 1. Clone and install
git clone <repo>
cd WHPC
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# 2. Configure (optional — only needed for live scraping)
cp .env.example .env
# edit .env to add your OUTSCRAPER_API_KEY

# 3. Seed sample data (no API keys needed)
python run.py seed

# 4. Start the web server
python run.py
# → http://127.0.0.1:5000
```

## Running live scrapes

```bash
# Crawl4AI — scrapes retailer websites directly (requires playwright)
python run.py scrape

# Outscraper — Google Shopping API (requires OUTSCRAPER_API_KEY in .env)
python run.py scrape-gs
```

## JSON API

| Endpoint | Description |
|---|---|
| `GET /api/products?category=Pregnancy&q=clearblue&page=1` | Paginated product list |
| `GET /api/products/<id>` | Single product with all listings |
| `GET /api/categories` | Category stats (count + min price) |
| `POST /api/scrape` | Trigger scrape (`{"source": "crawl4ai"}`) |

## Categories tracked

- Pregnancy
- Ovulation & Fertility
- STI / STD
- Menopause & FSH
- Thyroid
- Hormone Panel
- UTI
- Vaginal Health
- PCOS
- Breast Cancer Risk
- General Wellness

## Retailers / sources

| Source | Method |
|---|---|
| CVS | Crawl4AI (CSS) |
| Walgreens | Crawl4AI (CSS) |
| Amazon | Crawl4AI (CSS) or Outscraper |
| Target | Crawl4AI (CSS) |
| Everlywell | Crawl4AI (CSS) |
| LetsGetChecked | Crawl4AI (CSS) |
| Google Shopping | Outscraper API |

## Extending

- **Add a retailer**: add an entry to `SCRAPE_TARGETS` in `config.py` and a CSS schema in `scraper/crawl4ai_scraper.py`.
- **Add a category**: add to `TEST_CATEGORIES` in `config.py` and add a query to `SHOPPING_QUERIES` in `scraper/outscraper_client.py`.
- **Scheduled scraping**: uncomment the APScheduler block in `run.py` to run scrapes on a cron schedule.
