"""
Seed the database with a realistic sample dataset of women's health at-home tests.

This is useful for:
  - Prototyping / development without running a live scrape
  - Demoing the UI
  - Unit-testing the web app

Run via:  python run.py seed
"""
from data.models import db, Listing, Product

SEED_PRODUCTS = [
    # ── Pregnancy ─────────────────────────────────────────────────────────────
    {
        "name": "Clearblue Digital Pregnancy Test with Weeks Indicator (3 pack)",
        "brand": "Clearblue",
        "category": "Pregnancy",
        "description": "Tells you whether you are 1-2, 2-3 or 3+ weeks pregnant from conception.",
        "image_url": "",
        "tags": "hCG,digital,weeks indicator",
        "listings": [
            {"retailer": "CVS",       "price": 22.99, "original_price": 26.99, "url": "https://www.cvs.com/shop/clearblue-digital-pregnancy-test"},
            {"retailer": "Walgreens", "price": 21.49, "original_price": None,  "url": "https://www.walgreens.com/store/c/clearblue-digital-pregnancy-test"},
            {"retailer": "Amazon",    "price": 19.97, "original_price": 24.99, "url": "https://www.amazon.com/dp/B000052XCW"},
            {"retailer": "Target",    "price": 23.49, "original_price": None,  "url": "https://www.target.com/p/clearblue-digital-pregnancy-test"},
        ],
    },
    {
        "name": "First Response Early Result Pregnancy Test (3 pack)",
        "brand": "First Response",
        "category": "Pregnancy",
        "description": "Can detect pregnancy 6 days before your missed period.",
        "image_url": "",
        "tags": "hCG,early detection",
        "listings": [
            {"retailer": "CVS",       "price": 17.99, "original_price": None,  "url": "https://www.cvs.com/shop/first-response-pregnancy-test"},
            {"retailer": "Walgreens", "price": 16.99, "original_price": 19.99, "url": "https://www.walgreens.com/store/c/first-response-pregnancy-test"},
            {"retailer": "Amazon",    "price": 14.88, "original_price": 17.99, "url": "https://www.amazon.com/dp/B07MWH4VD4"},
        ],
    },
    # ── Ovulation & Fertility ─────────────────────────────────────────────────
    {
        "name": "Clearblue Advanced Digital Ovulation Test (20 count)",
        "brand": "Clearblue",
        "category": "Ovulation & Fertility",
        "description": "Identifies 4 fertile days by tracking estrogen and LH surge.",
        "image_url": "",
        "tags": "LH,estrogen,digital,ovulation",
        "listings": [
            {"retailer": "CVS",       "price": 49.99, "original_price": 54.99, "url": "https://www.cvs.com/shop/clearblue-advanced-ovulation-test"},
            {"retailer": "Amazon",    "price": 44.97, "original_price": 49.99, "url": "https://www.amazon.com/dp/B00KSHRLAI"},
            {"retailer": "Target",    "price": 49.99, "original_price": None,  "url": "https://www.target.com/p/clearblue-advanced-ovulation-test"},
        ],
    },
    {
        "name": "Inito Fertility Monitor & Hormone Tracker",
        "brand": "Inito",
        "category": "Ovulation & Fertility",
        "description": "Measures FSH, LH, estrogen and progesterone from a single urine test.",
        "image_url": "",
        "tags": "FSH,LH,estrogen,progesterone,fertility monitor",
        "listings": [
            {"retailer": "Inito (Direct)", "price": 149.00, "original_price": None, "url": "https://www.inito.com/"},
            {"retailer": "Amazon",         "price": 139.99, "original_price": 149.00,"url": "https://www.amazon.com/dp/B09NCPN3QS"},
        ],
    },
    {
        "name": "Proov PdG Progesterone Test (7 pack)",
        "brand": "Proov",
        "category": "Ovulation & Fertility",
        "description": "Tests PdG (progesterone metabolite) to confirm successful ovulation.",
        "image_url": "",
        "tags": "progesterone,PdG,ovulation confirmation",
        "listings": [
            {"retailer": "Proov (Direct)", "price": 39.00, "original_price": None,  "url": "https://www.proovtest.com/"},
            {"retailer": "Amazon",         "price": 36.99, "original_price": 39.00, "url": "https://www.amazon.com/dp/B07Q74MCGR"},
            {"retailer": "CVS",            "price": 39.99, "original_price": None,  "url": "https://www.cvs.com/shop/proov-pdg-test"},
        ],
    },
    # ── STI / STD ─────────────────────────────────────────────────────────────
    {
        "name": "Everlywell STI Test — Women (at-home collection kit)",
        "brand": "Everlywell",
        "category": "STI / STD",
        "description": "Tests for chlamydia, gonorrhea, trichomoniasis, and syphilis from home.",
        "image_url": "",
        "tags": "chlamydia,gonorrhea,syphilis,trichomoniasis,STI",
        "listings": [
            {"retailer": "Everlywell", "price": 149.00, "original_price": None,   "url": "https://www.everlywell.com/products/sti-test-for-women/"},
            {"retailer": "CVS",        "price": 149.00, "original_price": None,   "url": "https://www.cvs.com/shop/everlywell-sti-test"},
        ],
    },
    # ── Menopause & FSH ───────────────────────────────────────────────────────
    {
        "name": "Clearblue Menopause Stage Indicator (5 tests)",
        "brand": "Clearblue",
        "category": "Menopause & FSH",
        "description": "Tracks FSH levels to indicate menopause stage.",
        "image_url": "",
        "tags": "FSH,menopause,perimenopause",
        "listings": [
            {"retailer": "CVS",       "price": 29.99, "original_price": None,   "url": "https://www.cvs.com/shop/clearblue-menopause-test"},
            {"retailer": "Walgreens", "price": 27.99, "original_price": 29.99,  "url": "https://www.walgreens.com/store/c/clearblue-menopause-test"},
            {"retailer": "Amazon",    "price": 26.49, "original_price": 29.99,  "url": "https://www.amazon.com/dp/B0C5VQKC2F"},
        ],
    },
    {
        "name": "Everlywell Women's Health Test — Menopause Panel",
        "brand": "Everlywell",
        "category": "Menopause & FSH",
        "description": "Measures FSH, estradiol, and TSH to assess menopausal status and thyroid health.",
        "image_url": "",
        "tags": "FSH,estradiol,TSH,menopause,thyroid",
        "listings": [
            {"retailer": "Everlywell", "price": 199.00, "original_price": None,  "url": "https://www.everlywell.com/products/perimenopause-test/"},
        ],
    },
    # ── Thyroid ───────────────────────────────────────────────────────────────
    {
        "name": "LetsGetChecked Thyroid Test (TSH, T3, T4, TPO)",
        "brand": "LetsGetChecked",
        "category": "Thyroid",
        "description": "Comprehensive thyroid panel including TSH, Free T3, Free T4, and TPO antibodies.",
        "image_url": "",
        "tags": "TSH,T3,T4,TPO,thyroid,hypothyroid",
        "listings": [
            {"retailer": "LetsGetChecked", "price": 139.00, "original_price": None,   "url": "https://www.letsgetchecked.com/home-thyroid-test/"},
            {"retailer": "Walgreens",       "price": 139.00, "original_price": None,   "url": "https://www.walgreens.com/store/c/letsgetchecked-thyroid-test"},
        ],
    },
    # ── Hormone Panel ─────────────────────────────────────────────────────────
    {
        "name": "Everlywell Women's Health Test — Hormone Panel",
        "brand": "Everlywell",
        "category": "Hormone Panel",
        "description": "Tests estradiol, progesterone, testosterone, DHEA-S, LH, FSH, TSH.",
        "image_url": "",
        "tags": "estradiol,progesterone,testosterone,DHEA,LH,FSH,TSH",
        "listings": [
            {"retailer": "Everlywell", "price": 199.00, "original_price": None,   "url": "https://www.everlywell.com/products/womens-health-test/"},
            {"retailer": "CVS",        "price": 199.00, "original_price": None,   "url": "https://www.cvs.com/shop/everlywell-womens-health-test"},
        ],
    },
    # ── UTI ───────────────────────────────────────────────────────────────────
    {
        "name": "AZO Urinary Tract Infection Test Strips (3 count)",
        "brand": "AZO",
        "category": "UTI",
        "description": "Clinically tested to detect UTI symptoms with 99% accurate results in 2 minutes.",
        "image_url": "",
        "tags": "UTI,leukocytes,nitrites,urinary tract",
        "listings": [
            {"retailer": "CVS",       "price": 8.99,  "original_price": None,   "url": "https://www.cvs.com/shop/azo-uti-test-strips"},
            {"retailer": "Walgreens", "price": 7.99,  "original_price": 8.99,   "url": "https://www.walgreens.com/store/c/azo-uti-test-strips"},
            {"retailer": "Amazon",    "price": 6.97,  "original_price": 8.99,   "url": "https://www.amazon.com/dp/B0015AWQXM"},
            {"retailer": "Target",    "price": 8.49,  "original_price": None,   "url": "https://www.target.com/p/azo-uti-test-strips"},
        ],
    },
    # ── Vaginal Health ────────────────────────────────────────────────────────
    {
        "name": "Canestest Self-Test for Vaginal Infections",
        "brand": "Canestest",
        "category": "Vaginal Health",
        "description": "Distinguishes between bacterial vaginosis and thrush (yeast) by measuring vaginal pH.",
        "image_url": "",
        "tags": "BV,yeast,pH,vaginal health",
        "listings": [
            {"retailer": "CVS",       "price": 12.99, "original_price": None,   "url": "https://www.cvs.com/shop/canestest-vaginal-infection-test"},
            {"retailer": "Amazon",    "price": 11.49, "original_price": 12.99,  "url": "https://www.amazon.com/dp/B0776CBZWX"},
        ],
    },
    # ── PCOS ──────────────────────────────────────────────────────────────────
    {
        "name": "Everlywell PCOS Test Panel",
        "brand": "Everlywell",
        "category": "PCOS",
        "description": "Measures LH, FSH, estradiol, testosterone, and DHEA-S to help identify PCOS.",
        "image_url": "",
        "tags": "LH,FSH,estradiol,testosterone,DHEA,PCOS",
        "listings": [
            {"retailer": "Everlywell", "price": 199.00, "original_price": None,  "url": "https://www.everlywell.com/products/pcos-test/"},
        ],
    },
]


def seed_db() -> None:
    """Insert all seed products and their listings into the database."""
    added_products = 0
    added_listings = 0

    for p_data in SEED_PRODUCTS:
        listings_data = p_data.pop("listings")

        # Skip if already exists
        existing = Product.query.filter_by(
            name=p_data["name"], brand=p_data["brand"]
        ).first()
        if existing:
            product = existing
        else:
            product = Product(**p_data)
            db.session.add(product)
            db.session.flush()
            added_products += 1

        for l_data in listings_data:
            existing_listing = Listing.query.filter_by(
                product_id=product.id, retailer=l_data["retailer"]
            ).first()
            if existing_listing:
                existing_listing.price = l_data["price"]
                existing_listing.original_price = l_data.get("original_price")
                existing_listing.url = l_data["url"]
            else:
                listing = Listing(
                    product_id=product.id,
                    retailer=l_data["retailer"],
                    price=l_data["price"],
                    original_price=l_data.get("original_price"),
                    url=l_data["url"],
                    source="manual",
                )
                db.session.add(listing)
                added_listings += 1

        # Restore listings key in case dict is reused
        p_data["listings"] = listings_data

    db.session.commit()
    print(f"Seeded {added_products} products, {added_listings} listings.")
