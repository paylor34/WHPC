"""
Entry point for the Women's Health Price Comparison app.

Usage:
  python run.py              — start the web server (dev mode)
  python run.py seed         — seed database with sample data
  python run.py scrape       — run a live Crawl4AI scrape
  python run.py scrape-gs    — run an Outscraper Google Shopping scrape
"""
import sys


def main():
    from app import create_app
    app = create_app()

    command = sys.argv[1] if len(sys.argv) > 1 else "serve"

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

    else:  # serve
        print("Starting dev server at http://127.0.0.1:5000")
        app.run(debug=True, port=5000)


if __name__ == "__main__":
    main()
