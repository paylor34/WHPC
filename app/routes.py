"""
Flask routes for the Women's Health Price Comparison directory.

Endpoints:
  GET  /                      — Home: category grid
  GET  /category/<name>       — Products in a category
  GET  /product/<id>          — Single product with all retailer prices
  GET  /compare?ids=1,2,3     — Side-by-side comparison (up to 4 products)
  GET  /search?q=             — Full-text search
  GET  /api/products          — JSON list (supports ?category=&q= filters)
  GET  /api/products/<id>     — Single product JSON
  GET  /api/categories        — Category stats JSON
  GET  /api/scheduler         — Scheduled job list + next run times
  POST /api/scrape            — Trigger a background scrape (dev use)
"""
from flask import Blueprint, abort, jsonify, render_template, request

from config import TEST_CATEGORIES
from data.models import Listing, Product, ScrapeLog, db

bp = Blueprint("main", __name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _category_stats() -> list[dict]:
    """Return category name + product count + min price for the home page."""
    stats = []
    for cat in TEST_CATEGORIES:
        products = Product.query.filter_by(category=cat).all()
        if not products:
            continue
        prices = [p.lowest_price for p in products if p.lowest_price is not None]
        stats.append({
            "name": cat,
            "count": len(products),
            "min_price": min(prices) if prices else None,
        })
    return stats


# ── Pages ─────────────────────────────────────────────────────────────────────

@bp.route("/")
def home():
    from flask import current_app
    categories = _category_stats()
    recent_logs = ScrapeLog.query.order_by(ScrapeLog.started_at.desc()).limit(5).all()

    scheduler = getattr(current_app, "scheduler", None)
    scheduled_jobs = []
    if scheduler and scheduler.running:
        for job in scheduler.get_jobs():
            scheduled_jobs.append({
                "name": job.name,
                "next_run": job.next_run_time,
            })

    return render_template(
        "index.html",
        categories=categories,
        recent_logs=recent_logs,
        scheduled_jobs=scheduled_jobs,
    )


@bp.route("/category/<path:category_name>")
def category(category_name: str):
    sort = request.args.get("sort", "price")   # price | name | discount
    products = Product.query.filter_by(category=category_name).all()
    if not products and category_name not in TEST_CATEGORIES:
        abort(404)

    if sort == "name":
        products.sort(key=lambda p: p.name.lower())
    elif sort == "discount":
        products.sort(
            key=lambda p: max(
                (l.discount_pct or 0 for l in p.listings), default=0
            ),
            reverse=True,
        )
    else:  # price
        products.sort(key=lambda p: (p.lowest_price is None, p.lowest_price or 0))

    return render_template(
        "category.html",
        category=category_name,
        products=products,
        sort=sort,
        categories=TEST_CATEGORIES,
    )


@bp.route("/product/<int:product_id>")
def product(product_id: int):
    p = Product.query.get_or_404(product_id)
    listings = (
        Listing.query.filter_by(product_id=product_id)
        .order_by(Listing.price.asc())
        .all()
    )
    related = (
        Product.query.filter(
            Product.category == p.category, Product.id != p.id
        )
        .limit(4)
        .all()
    )
    return render_template(
        "product.html", product=p, listings=listings, related=related
    )


@bp.route("/compare")
def compare():
    raw_ids = request.args.get("ids", "")
    ids = [int(i) for i in raw_ids.split(",") if i.strip().isdigit()][:4]
    products = [Product.query.get(i) for i in ids if Product.query.get(i)]
    all_retailers = sorted(
        {l.retailer for p in products for l in p.listings}
    )
    return render_template(
        "compare.html", products=products, all_retailers=all_retailers
    )


@bp.route("/search")
def search():
    q = request.args.get("q", "").strip()
    if not q:
        return render_template("search.html", results=[], q=q)

    results = (
        Product.query.filter(
            db.or_(
                Product.name.ilike(f"%{q}%"),
                Product.brand.ilike(f"%{q}%"),
                Product.description.ilike(f"%{q}%"),
                Product.tags.ilike(f"%{q}%"),
            )
        )
        .order_by(Product.name)
        .limit(50)
        .all()
    )
    return render_template("search.html", results=results, q=q)


# ── JSON API ──────────────────────────────────────────────────────────────────

@bp.route("/api/products")
def api_products():
    q = request.args.get("q", "")
    category = request.args.get("category", "")
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 20)), 100)

    query = Product.query
    if category:
        query = query.filter_by(category=category)
    if q:
        query = query.filter(
            db.or_(
                Product.name.ilike(f"%{q}%"),
                Product.brand.ilike(f"%{q}%"),
            )
        )

    paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "page": page,
        "per_page": per_page,
        "total": paginated.total,
        "products": [p.to_dict() for p in paginated.items],
    })


@bp.route("/api/products/<int:product_id>")
def api_product(product_id: int):
    p = Product.query.get_or_404(product_id)
    return jsonify(p.to_dict())


@bp.route("/api/categories")
def api_categories():
    return jsonify(_category_stats())


@bp.route("/api/scheduler")
def api_scheduler():
    """Return the status of all scheduled jobs."""
    from flask import current_app
    scheduler = getattr(current_app, "scheduler", None)
    if scheduler is None:
        return jsonify({"running": False, "jobs": []})

    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
        })
    return jsonify({"running": scheduler.running, "jobs": jobs})


@bp.route("/api/scrape", methods=["POST"])
def api_scrape():
    """
    Trigger a scrape run (development/admin use only).
    In production, this should be behind auth and run via a task queue.
    """
    source = request.json.get("source", "crawl4ai")  # crawl4ai | outscraper

    # Lazy imports to keep startup fast
    if source == "outscraper":
        from config import Config
        from scraper.outscraper_client import OutscraperShopping
        from scraper.importer import upsert_products, log_scrape

        client = OutscraperShopping(api_key=Config.OUTSCRAPER_API_KEY)
        products = client.search_all_categories()
        created, updated = upsert_products(products, source="outscraper")
        log_scrape("all", "outscraper", len(products), updated)
    else:
        import asyncio
        from config import SCRAPE_TARGETS
        from scraper.crawl4ai_scraper import scrape_all
        from scraper.importer import upsert_products, log_scrape

        products = asyncio.run(scrape_all(SCRAPE_TARGETS))
        created, updated = upsert_products(products, source="crawl4ai")
        log_scrape("all", "crawl4ai", len(products), updated)

    return jsonify({"status": "ok", "found": len(products), "updated": updated})
