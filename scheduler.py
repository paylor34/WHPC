"""
Price-refresh scheduler for the Women's Health Price Comparison app.

Uses APScheduler's BackgroundScheduler so scrapes run in-process alongside
the Flask dev server (or any WSGI server that starts the Flask app).

For production, prefer running this as a separate process or a cron job
rather than embedding it in the web worker.

The Crawl4AI scrape job runs every REFRESH_INTERVAL_HOURS and writes to
ScrapeLog so you can see data freshness on the home page.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

log = logging.getLogger(__name__)


def _run_crawl4ai(app) -> None:
    """Synchronous wrapper — APScheduler jobs must be non-async."""
    from config import SCRAPE_TARGETS
    from scraper.crawl4ai_scraper import scrape_all
    from scraper.importer import log_scrape, upsert_products

    started = datetime.now(timezone.utc)
    log.info("Scheduled Crawl4AI scrape starting")
    try:
        products = asyncio.run(scrape_all(SCRAPE_TARGETS))
        with app.app_context():
            created, updated = upsert_products(products, source="crawl4ai")
            log_scrape(
                retailer="all",
                source="crawl4ai",
                products_found=len(products),
                products_updated=updated,
                success=True,
            )
        log.info(
            "Crawl4AI scrape done: %d found, %d updated (%.1fs)",
            len(products),
            updated,
            (datetime.now(timezone.utc) - started).total_seconds(),
        )
    except Exception as exc:
        log.exception("Crawl4AI scrape failed: %s", exc)
        with app.app_context():
            log_scrape(
                retailer="all",
                source="crawl4ai",
                products_found=0,
                products_updated=0,
                errors=str(exc),
                success=False,
            )


def start_scheduler(app, interval_hours: int = 24) -> BackgroundScheduler:
    """
    Attach and start the background price-refresh scheduler.

    Args:
        app: The Flask application instance.
        interval_hours: How often to run the Crawl4AI scrape (hours).

    Returns:
        The running BackgroundScheduler instance (call .shutdown() to stop).

    Jobs added:
        crawl4ai_refresh  — every `interval_hours` hours

    The job is also scheduled to run once shortly after startup
    (first_run_delay=300s = 5 minutes) so a fresh deployment populates
    data without waiting a full interval.
    """
    scheduler = BackgroundScheduler(timezone="UTC")

    # ── Crawl4AI job ──────────────────────────────────────────────────────────
    scheduler.add_job(
        func=_run_crawl4ai,
        args=[app],
        trigger=IntervalTrigger(hours=interval_hours),
        id="crawl4ai_refresh",
        name="Crawl4AI retailer scrape",
        replace_existing=True,
        # Start 5 minutes after server boot so startup isn't blocked
        next_run_time=_in_seconds(300),
        misfire_grace_time=3600,   # allow up to 1h late if server was down
    )
    log.info(
        "Scheduled: crawl4ai_refresh every %dh (first run in 5 min)", interval_hours
    )

    scheduler.start()
    log.info("BackgroundScheduler started")
    return scheduler


def _in_seconds(seconds: int):
    """Return a datetime `seconds` from now (UTC), used for next_run_time."""
    from datetime import timedelta
    return datetime.now(timezone.utc) + timedelta(seconds=seconds)
