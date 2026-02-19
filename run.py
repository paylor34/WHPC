"""
Entry point for the Women's Health Price Comparison app.

Usage:
  python run.py              — start the web server + background scheduler
  python run.py seed         — seed database with sample data
  python run.py scrape       — run a one-off Crawl4AI scrape
  python run.py scrape-gs    — run a one-off Outscraper Google Shopping scrape
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

    elif command == "scrape-gs":
        with app.app_context():
            from config import Config
            from scraper.outscraper_client import OutscraperShopping
            from scraper.importer import upsert_products, log_scrape
            from rich import print as rprint

            if not Config.OUTSCRAPER_API_KEY:
                print("ERROR: Set OUTSCRAPER_API_KEY in your .env file.")
                sys.exit(1)

            rprint("[bold]Running Outscraper Google Shopping scrape…[/bold]")
            client = OutscraperShopping(api_key=Config.OUTSCRAPER_API_KEY)
            products = client.search_all_categories()
            created, updated = upsert_products(products, source="outscraper")
            log_scrape("all", "outscraper", len(products), updated)
            rprint(f"[green]Done.[/green] {len(products)} found, {created} new, {updated} updated.")

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
        print("Starting dev server + background scheduler at http://127.0.0.1:5000")
        print("Prices will refresh every", app.config.get("REFRESH_INTERVAL_HOURS", 24), "hours.")
        # use_reloader=False prevents APScheduler from starting twice in debug mode
        app.run(debug=True, port=5000, use_reloader=False)


if __name__ == "__main__":
    main()
