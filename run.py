"""
Entry point for the Women's Health Price Comparison app.

Usage:
  python run.py              — start the web server + background scheduler
  python run.py seed         — seed database with sample data
  python run.py scrape       — run a one-off Crawl4AI scrape
  python run.py export       — export DB → data/exports/products.json + listings.csv
  python run.py import       — import data/exports/listings.csv into the database
  python run.py jobs         — list scheduled jobs and their next run times
"""
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s — %(message)s",
)


def main():
    from app import create_app

    command = sys.argv[1] if len(sys.argv) > 1 else "serve"

    # Scheduler runs only when serving; not needed for one-off commands
    app = create_app(start_scheduler=(command == "serve"))

    if command == "seed":
        with app.app_context():
            from data.seed import seed_db
            seed_db()
        print("Done. Run `python run.py` to start the web server.")

    elif command == "scrape":
        import asyncio
        with app.app_context():
            from config import SCRAPE_TARGETS
            from scraper.crawl4ai_scraper import scrape_all
            from scraper.importer import upsert_products, log_scrape
            from rich import print as rprint

            rprint("[bold]Running Crawl4AI scrape across all targets…[/bold]")
            products = asyncio.run(scrape_all(SCRAPE_TARGETS))
            created, updated = upsert_products(products, source="crawl4ai")
            log_scrape("all", "crawl4ai", len(products), updated)
            rprint(f"[green]Done.[/green] {len(products)} found, {created} new, {updated} updated.")

    elif command == "import":
        with app.app_context():
            from data.import_csv import import_from_csv
            from rich import print as rprint
            rprint("[bold]Importing from data/exports/listings.csv…[/bold]")
            created, upserted = import_from_csv()
            rprint(f"[green]Done.[/green] {created} new products, {upserted} listings upserted.")

    elif command == "export":
        with app.app_context():
            from data.export import export_all
            products, listings = export_all()
            print(f"Exported {products} products and {listings} listings to data/exports/")
            print("  data/exports/products.json")
            print("  data/exports/listings.csv")

    elif command == "jobs":
        # List APScheduler jobs and their next run times
        if not hasattr(app, "scheduler"):
            print("Scheduler not running (start the server first, or re-run with no args).")
            sys.exit(1)
        jobs = app.scheduler.get_jobs()
        if not jobs:
            print("No scheduled jobs found.")
        for job in jobs:
            print(f"  {job.id:30s}  next: {job.next_run_time}")

    else:  # serve
        port = int(app.config.get("PORT", 5001))
        print(f"Starting dev server + background scheduler at http://127.0.0.1:{port}")
        print("Prices will refresh every", app.config.get("REFRESH_INTERVAL_HOURS", 24), "hours.")
        # use_reloader=False prevents APScheduler from starting twice in debug mode
        app.run(debug=True, port=port, use_reloader=False)


if __name__ == "__main__":
    main()
