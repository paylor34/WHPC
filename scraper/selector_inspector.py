"""
Selector Inspector — run this locally to discover real CSS selectors on each
retailer's search page.

It opens each URL in a visible (headed) Playwright browser, waits for products
to render, then tries a ranked list of candidate selectors and reports which
ones match live elements.  It also saves a trimmed HTML snapshot so you can
inspect it manually.

Usage:
    python -m scraper.selector_inspector                  # all retailers
    python -m scraper.selector_inspector Amazon Everlywell # specific ones

Requirements:
    pip install playwright rich
    playwright install chromium
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from rich import print as rprint
from rich.table import Table

try:
    from playwright.async_api import async_playwright, Page
except ImportError:
    print("ERROR: pip install playwright && playwright install chromium")
    sys.exit(1)

# ── Candidate selectors to probe per retailer ─────────────────────────────────
# For each field we try selectors in priority order; first match wins.
# "wait_for" is the selector Playwright waits on before probing.

RETAILER_PROBES = {
    "CVS": {
        "url": "https://www.cvs.com/search?searchTerm=women+health+test",
        "wait_for": "text=results",
        "candidates": {
            "baseSelector":    [".product-list-item", ".product-card", "[class*='product-item']"],
            "name":            [".product-name", ".product-title", "[class*='product-name']", "h3"],
            "price":           [".price", ".product-price", "[class*='price']"],
            "original_price":  ["[class*='strike']", "[class*='was']", "del", "s"],
            "url":             ["a.product-link", "a[href*='/shop/']", "h3 a", ".product-name a"],
            "image_url":       ["img.product-image", "img[class*='product']", "picture img"],
            "in_stock":        [".add-to-cart", "[class*='add-to-cart']", "button[class*='cart']"],
        },
    },
    "Walgreens": {
        "url": "https://www.walgreens.com/search/results.jsp?Ntt=women+health+test",
        "wait_for": "text=results",
        "candidates": {
            "baseSelector":    [".product-tile", ".product-card", "[class*='product-tile']"],
            "name":            [".product-name", ".product-tile-name", "[class*='product-name']", "p.bold"],
            "price":           [".product-price", ".regular-price", "[class*='price']"],
            "original_price":  ["[class*='strike']", "[class*='was']", "del"],
            "url":             ["a.product-tile-link", "a[href*='/store/']", ".product-name a"],
            "image_url":       ["img.product-image", "img[class*='product']", "picture img"],
            "in_stock":        [".add-to-cart-btn", "button[class*='cart']", "[class*='add-to-cart']"],
        },
    },
    "Amazon": {
        "url": "https://www.amazon.com/s?k=women+at+home+health+test",
        "wait_for": "[data-component-type='s-search-result']",
        "candidates": {
            "baseSelector":    [
                "[data-component-type='s-search-result']",
                "div.s-result-item[data-asin]",
            ],
            "name":            [
                "h2 span.a-text-normal",
                "h2 .a-size-base-plus",
                "h2 span",
            ],
            "price":           [
                ".a-price[data-a-size='xl'] .a-offscreen",
                ".a-price .a-offscreen",
                "[data-a-color='base'] .a-offscreen",
            ],
            "original_price":  [
                ".a-price[data-a-strike='true'] .a-offscreen",
                "span.a-price.a-text-price .a-offscreen",
            ],
            "url":             [
                "h2 a.a-link-normal",
                "a.s-no-outline",
                "h2 a",
            ],
            "image_url":       ["img.s-image", "img[class*='s-image']"],
            "in_stock":        [
                "[data-cy='add-to-cart-button-announce']",
                ".a-declarative[data-action='add-to-cart']",
                "input[name='add-to-cart']",
            ],
        },
    },
    "Target": {
        "url": "https://www.target.com/s?searchTerm=womens+health+test",
        "wait_for": "[data-test='product-details']",
        "candidates": {
            "baseSelector":    [
                "[data-test='product-details']",
                "[data-test='product-list-item']",
                "li[data-test*='product']",
            ],
            "name":            [
                "[data-test='product-title']",
                "a[data-test='product-title']",
            ],
            "price":           [
                "[data-test='current-price'] span",
                "[data-test='current-price']",
                "[data-test='product-price']",
            ],
            "original_price":  [
                "[data-test='reg-price']",
                "[data-test='regular-price']",
            ],
            "url":             ["a[href*='/p/']", "a[data-test='product-title']"],
            "image_url":       [
                "img[data-test='product-image']",
                "picture source[type='image/webp']",
                "img",
            ],
            "in_stock":        [
                "[data-test='shippingBlock']",
                "button[data-test='addToCartButton']",
            ],
        },
    },
    "Everlywell": {
        "url": "https://www.everlywell.com/collections/womens-health",
        "wait_for": "text=test",
        "candidates": {
            "baseSelector":    [
                ".product-item",
                ".ProductCard",
                ".product-card",
                "li.grid__item",
                "[class*='ProductCard']",
                "[class*='product-card']",
            ],
            "name":            [
                ".product-item__title",
                ".ProductCard__title",
                ".card__heading",
                "h3[class*='title']",
                "[class*='product-name']",
            ],
            "price":           [
                ".price .price__regular .price-item--regular",
                ".price-item.price-item--regular",
                ".price .money",
                "[class*='price'] span",
            ],
            "original_price":  [
                ".price__compare .price-item--regular",
                ".price--compare .money",
                "s.price-item",
            ],
            "url":             [
                "a.product-item__link",
                ".card__heading a",
                "a[href*='/products/']",
            ],
            "image_url":       [
                "img.product-item__image",
                ".card__media img",
                "img[class*='product']",
                "picture img",
            ],
        },
    },
    "LetsGetChecked": {
        "url": "https://www.letsgetchecked.com/us/en/women/",
        "wait_for": "text=test",
        "candidates": {
            "baseSelector":    [
                ".test-card",
                ".product-card",
                ".TestCard",
                "[class*='TestCard']",
                "[class*='test-card']",
                "article",
            ],
            "name":            [
                ".test-card__title",
                ".TestCard__title",
                "h3[class*='title']",
                "[class*='card-title']",
            ],
            "price":           [
                ".test-card__price",
                ".TestCard__price",
                "[class*='price']",
            ],
            "url":             [
                "a.test-card__link",
                ".TestCard a",
                "a[href*='/test/']",
                "article a",
            ],
            "image_url":       [
                "img",
                "picture img",
                "[class*='image'] img",
            ],
        },
    },
}

SNAPSHOT_DIR = Path(__file__).parent.parent / ".selector_snapshots"


async def probe_page(name: str, config: dict) -> dict[str, str]:
    """
    Open the page in a headed browser, wait for products to appear,
    then test each candidate selector and return the first match per field.
    Also saves an HTML snapshot.
    """
    results: dict[str, str] = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=200)
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        page: Page = await ctx.new_page()

        rprint(f"[cyan]  Opening[/cyan] {config['url']}")
        await page.goto(config["url"], timeout=30_000)

        # Wait for products or a reasonable timeout
        try:
            await page.wait_for_selector(config["wait_for"], timeout=15_000)
        except Exception:
            rprint(f"  [yellow]⚠ wait_for '{config['wait_for']}' timed out — probing anyway[/yellow]")

        # Extra time for lazy-loads
        await page.wait_for_timeout(3_000)

        # Scroll to trigger lazy-loading
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(1_500)

        # Save HTML snapshot
        SNAPSHOT_DIR.mkdir(exist_ok=True)
        snapshot_path = SNAPSHOT_DIR / f"{name.lower().replace(' ', '_')}.html"
        html = await page.content()
        snapshot_path.write_text(html, encoding="utf-8")
        rprint(f"  [dim]HTML snapshot saved → {snapshot_path}[/dim]")

        # Probe each field
        for field, selectors in config["candidates"].items():
            for sel in selectors:
                try:
                    el = page.locator(sel).first
                    count = await page.locator(sel).count()
                    if count > 0:
                        results[field] = sel
                        break
                except Exception:
                    continue
            else:
                results[field] = "NOT FOUND"

        await browser.close()

    return results


def print_report(name: str, found: dict[str, str]) -> None:
    table = Table(title=f"[bold]{name}[/bold] — selector results", show_lines=True)
    table.add_column("Field", style="cyan")
    table.add_column("Winning selector", style="white")
    table.add_column("Status")

    for field, sel in found.items():
        status = "[green]✓[/green]" if sel != "NOT FOUND" else "[red]✗ not found[/red]"
        table.add_row(field, sel, status)

    rprint(table)


async def main() -> None:
    targets = sys.argv[1:] if len(sys.argv) > 1 else list(RETAILER_PROBES.keys())
    unknown = [t for t in targets if t not in RETAILER_PROBES]
    if unknown:
        print(f"Unknown retailers: {unknown}. Valid: {list(RETAILER_PROBES.keys())}")
        sys.exit(1)

    for name in targets:
        rprint(f"\n[bold magenta]── {name} ──[/bold magenta]")
        found = await probe_page(name, RETAILER_PROBES[name])
        print_report(name, found)
        rprint(
            f"\n[dim]Paste the winning selectors into RETAILER_SCHEMAS "
            f"in scraper/crawl4ai_scraper.py[/dim]\n"
        )


if __name__ == "__main__":
    asyncio.run(main())
