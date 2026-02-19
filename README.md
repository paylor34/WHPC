# Women's Health Price Comparison (WHPC)

A prototype price comparison directory for women's health at-home tests, built with Python + Flask and Crawl4AI.

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

## How the scraper works

### Crawl4AI (`scraper/crawl4ai_scraper.py`)

Crawl4AI launches a headless Playwright (Chromium) browser, navigates to a retailer's search/category page, waits for JavaScript to render, then extracts structured product data using CSS selectors defined per-retailer in `RETAILER_SCHEMAS`.

- **CSS strategy** — fast, deterministic, fragile to DOM changes
- **LLM strategy** — pass `use_llm=True`; Crawl4AI sends the page to an LLM (e.g. GPT-4o-mini) with a structured extraction prompt. Slower but robust to redesigns.

## Quickstart

```bash
# 1. Clone and install
git clone <repo>
cd WHPC
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# 2. Configure (optional)
cp .env.example .env
# edit .env as needed

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
| Amazon | Crawl4AI (CSS) |
| Target | Crawl4AI (CSS) |
| Everlywell | Crawl4AI (CSS) |
| LetsGetChecked | Crawl4AI (CSS) |
| Labcorp On Demand | Crawl4AI (CSS) |
| Quest Diagnostics | Crawl4AI (CSS) |

### About Labcorp On Demand & Quest Diagnostics

**Labcorp On Demand** (`labcorpondemand.com`) and **Quest Diagnostics QuestDirect** (`questdirect.questdiagnostics.com`) are direct-to-consumer lab testing portals where customers can order blood/urine panels and at-home collection kits without a doctor's order. Both carry a broad catalog of women's health tests (hormones, STIs, thyroid, menopause panels, etc.) and list prices directly on their sites, making them valuable pricing sources.

> **Note:** Both sites are React SPAs with generated class names. If CSS selectors break after a site redesign, run `python -m scraper.selector_inspector "Labcorp On Demand" "Quest Diagnostics"` to rediscover working selectors, or set `use_llm=True` in `scrape_all()` for automatic LLM-based extraction.

## Extending

- **Add a retailer**: add an entry to `SCRAPE_TARGETS` in `config.py` and a CSS schema in `scraper/crawl4ai_scraper.py`.
- **Add a category**: add to `TEST_CATEGORIES` in `config.py`.
- **Scheduled scraping**: the APScheduler block in `scheduler.py` runs scrapes on a configurable interval (default: 24 h).
