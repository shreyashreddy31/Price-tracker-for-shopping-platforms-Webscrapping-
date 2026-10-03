"""
Smart Price Tracker - Backend API v7
100% FREE scraping using Selenium + undetected-chromedriver + BeautifulSoup

WHY THIS WORKS when other methods fail:
  - Amazon/Flipkart detect bots via: missing JS execution, TLS fingerprinting,
    missing cookies, and navigator.webdriver flag
  - undetected-chromedriver patches a REAL Chrome browser to remove all
    automation signals, so the site thinks it's a normal user
  - BeautifulSoup then parses the real page HTML to extract prices

Strategies (tried in order):
  1. Selenium + undetected-chromedriver (most reliable, FREE)
  2. httpx session simulation with cookies (FREE, works for Flipkart/others)
  3. Direct httpx request (FREE, last resort)
"""

import re
import json
import random
import os
import asyncio
import time
import sqlite3
from datetime import datetime
from urllib.parse import urlparse, quote_plus
from typing import Optional, List
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
from dotenv import load_dotenv

load_dotenv()

# ─── Optional imports ─────────────────────────────────────────────────────────
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("[WARN] Selenium not installed. Install with:")
    print("       pip install selenium")

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    print("[WARN] BeautifulSoup not installed. Install with: pip install beautifulsoup4 lxml")

# Thread pool for running sync Selenium in async FastAPI
_executor = ThreadPoolExecutor(max_workers=2)

app = FastAPI(title="Smart Price Tracker API", version="6.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Config ───────────────────────────────────────────────────────────────────
# All strategies are FREE — no API keys required!
# For best results, install Playwright:
#   pip install playwright && playwright install chromium

# ─── SQLite Price History Database ────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "price_history.db")

def _init_db():
    """Create the price_history table if it doesn't exist."""
    conn = sqlite3.connect(DB_PATH)
    # Price history table (keeps all scraped points)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            platform TEXT NOT NULL,
            title TEXT NOT NULL,
            price REAL NOT NULL,
            original_price REAL,
            scraped_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_url ON price_history(url)")

    # Watches table: user requests to watch a URL until a target price
    conn.execute("""
        CREATE TABLE IF NOT EXISTS watches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            platform TEXT,
            title TEXT,
            target_price REAL NOT NULL,
            email TEXT NOT NULL,
            active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            last_checked TEXT,
            triggered_at TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_watches_url ON watches(url)")

    conn.commit()
    conn.close()
    print(f"[DB] Price history + watches database ready at {DB_PATH}")

_init_db()

def _save_price_point(url: str, platform: str, title: str, price: float, original_price: float = None):
    """Save a scraped price data point to the database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO price_history (url, platform, title, price, original_price, scraped_at) VALUES (?, ?, ?, ?, ?, ?)",
            (url, platform, title, price, original_price, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        print(f"[DB] Saved price point: ₹{price} for {platform}")
    except Exception as e:
        print(f"[DB] Error saving price: {e}")

def _get_price_history(url: str) -> List[dict]:
    """Retrieve all price history for a URL, sorted by time."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT platform, title, price, original_price, scraped_at FROM price_history WHERE url = ? ORDER BY scraped_at ASC",
            (url,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[DB] Error reading history: {e}")
        return []


# ─── Watches (price alerts) helpers ─────────────────────────────────────────
def _create_watch(url: str, target_price: float, email: str, title: str = None, platform: str = None):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO watches (url, platform, title, target_price, email, active, created_at) VALUES (?, ?, ?, ?, ?, 1, ?)",
            (url, platform or detect_platform(url), title or "", target_price, email, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        print(f"[DB] Created watch for {url} <= ₹{target_price} -> {email}")
        return True
    except Exception as e:
        print(f"[DB] Error creating watch: {e}")
        return False


def _list_watches() -> List[dict]:
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM watches ORDER BY created_at DESC").fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[DB] Error listing watches: {e}")
        return []


def _delete_watch(watch_id: int) -> bool:
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("DELETE FROM watches WHERE id = ?", (watch_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[DB] Error deleting watch: {e}")
        return False

# ─── Models ───────────────────────────────────────────────────────────────────

class ProductRequest(BaseModel):
    url: str
    force_refresh: bool = False

class ComparisonResult(BaseModel):
    platform: str
    title: str
    price: float
    image_url: str = ""
    product_url: str = ""
    rating: Optional[float] = None

class ProductResponse(BaseModel):
    platform: str
    title: str
    current_price: float
    currency: str
    original_price: Optional[float] = None
    discount_percent: Optional[float] = None
    image_url: str
    availability: str
    rating: Optional[float] = None
    review_count: Optional[int] = None
    seller_verified: bool
    scraped_at: str
    comparison: list = []  # Real prices from other platforms
    price_history: list = []  # Genuine historical price data points from DB

class WatchRequest(BaseModel):
    url: str
    target_price: float
    email: str

class WatchResponse(BaseModel):
    id: int
    url: str
    platform: str
    title: str
    target_price: float
    email: str
    active: int
    created_at: str
    last_checked: Optional[str] = None
    triggered_at: Optional[str] = None

# ─── Platform Detection ───────────────────────────────────────────────────────

PLATFORM_PATTERNS = {
    "amazon":   [r"amazon\.in", r"amazon\.com"],
    "flipkart": [r"flipkart\.com"],
    "myntra":   [r"myntra\.com"],
    "snapdeal": [r"snapdeal\.com"],
    "meesho":   [r"meesho\.com"],
    "jiomart":  [r"jiomart\.com"],
    "croma":    [r"croma\.com"],
    "tatacliq": [r"tatacliq\.com"],
}

def detect_platform(url: str) -> str:
    hostname = urlparse(url).netloc.lower().replace("www.", "")
    for platform, patterns in PLATFORM_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, hostname):
                return platform
    return "unknown"

def validate_url(url: str) -> bool:
    try:
        r = urlparse(url)
        return all([r.scheme in ("http", "https"), r.netloc])
    except Exception:
        return False

# ─── Helpers ─────────────────────────────────────────────────────────────────

def clean_price(text) -> Optional[float]:
    if not text:
        return None
    text = re.sub(r"[₹$€£¥Rs.,\s]", "", str(text))
    match = re.search(r"(\d+(?:\.\d{1,2})?)", text)
    if match:
        val = float(match.group(1))
        if 1 <= val <= 1000000:
            return val
    return None

def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()

def extract_asin(url: str) -> Optional[str]:
    """Extract Amazon ASIN from URL."""
    patterns = [
        r"/dp/([A-Z0-9]{10})",
        r"/gp/product/([A-Z0-9]{10})",
        r"/product/([A-Z0-9]{10})",
        r"asin=([A-Z0-9]{10})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None

# ─── Fetching Strategies (ALL FREE — no API keys) ─────────────────────────────

# ── Shared: rotating user agents + realistic headers ──────────────────────────

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

def get_stealth_headers(referer: str = "https://www.google.com/") -> dict:
    ua = random.choice(USER_AGENTS)
    is_chrome = "Chrome" in ua
    return {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7,hi;q=0.6",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": referer,
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
        **({"Sec-Ch-Ua": '"Chromium";v="125", "Google Chrome";v="125", "Not.A/Brand";v="24"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-User": "?1"} if is_chrome else {}),
    }


# ── STRATEGY 1: Selenium + undetected-chromedriver (BEST, FREE) ──────────────

def _create_stealth_driver():
    """
    Create a Chrome instance with stealth settings using regular Selenium.
    Uses Chrome DevTools Protocol to hide automation signals.
    """
    import platform as plat

    options = ChromeOptions()
    # Use old --headless flag (better compatibility + less detectable than --headless=new)
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--lang=en-IN")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-popup-blocking")
    options.add_argument(f"--user-agent={random.choice(USER_AGENTS)}")

    # KEY: Remove automation indicators
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # Don't block images — Amazon needs them for page to fully render
    prefs = {
        "profile.default_content_setting_values.notifications": 2,
    }
    options.add_experimental_option("prefs", prefs)

    # Use the correct chromedriver for Apple Silicon
    driver_path = None
    if plat.machine() == "arm64" and plat.system() == "Darwin":
        candidate = "/tmp/chromedriver-mac-arm64/chromedriver"
        if os.path.exists(candidate):
            driver_path = candidate

    if driver_path:
        service = ChromeService(executable_path=driver_path)
        driver = webdriver.Chrome(service=service, options=options)
    else:
        driver = webdriver.Chrome(options=options)

    # Remove navigator.webdriver flag via Chrome DevTools Protocol
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                    { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                    { name: 'Native Client', filename: 'internal-nacl-plugin' },
                ]
            });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-IN', 'en-GB', 'en'] });
            window.chrome = { runtime: { onMessage: { addListener: () => {} }, sendMessage: () => {} } };
            // Override permissions query
            const origQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (params) =>
                params.name === 'notifications'
                    ? Promise.resolve({ state: Notification.permission })
                    : origQuery(params);
        """
    })

    # Set realistic viewport
    driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
        "mobile": False,
        "width": 1920,
        "height": 1080,
        "deviceScaleFactor": 1,
    })

    return driver


def _fetch_with_selenium_sync(url: str, platform: str) -> Optional[str]:
    """
    Synchronous Selenium fetch (runs in a thread pool).
    Uses regular Chrome with stealth patches to look like a real user.
    """
    if not SELENIUM_AVAILABLE:
        return None

    driver = None
    try:
        print(f"[Selenium] Launching stealth Chrome for {url[:70]}...")
        driver = _create_stealth_driver()

        # Set page load timeout
        driver.set_page_load_timeout(30)

        # First visit Google to get a realistic referer + warm up cookies
        print("[Selenium] Step 1: Visiting Google first (for realistic referer)...")
        try:
            driver.get("https://www.google.com/search?q=amazon+india")
            time.sleep(random.uniform(1.5, 3.0))
        except Exception:
            pass  # Not critical if this times out

        # Now navigate to the actual product page
        print(f"[Selenium] Step 2: Navigating to product page...")
        driver.get(url)

        # Wait for the page to start rendering
        time.sleep(3)

        # Check current URL (Amazon may have redirected)
        current_url = driver.current_url
        print(f"[Selenium] Current URL: {current_url[:80]}")

        # Wait for key elements to load
        wait = WebDriverWait(driver, 20)
        found_element = False
        if platform == "amazon":
            for selector in [
                "#productTitle",
                "#corePrice_feature_div",
                ".a-price-whole",
                "#priceblock_ourprice",
                "#title",
            ]:
                try:
                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    print(f"[Selenium] ✓ Found element: {selector}")
                    found_element = True
                    break
                except Exception:
                    continue
        elif platform == "flipkart":
            for selector in ["._30jeq3", "._16Jk6d", ".Nx9bqj", ".CEmiEU", "h1"]:
                try:
                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    found_element = True
                    break
                except Exception:
                    continue
        else:
            time.sleep(4)
            found_element = True

        if not found_element:
            print("[Selenium] ⚠ No key elements found, waiting extra time...")
            time.sleep(5)

        # Scroll down to trigger lazy loading
        driver.execute_script("window.scrollTo(0, 500);")
        time.sleep(1)
        driver.execute_script("window.scrollTo(0, 1000);")
        time.sleep(1)

        html = driver.page_source
        page_title = driver.title
        print(f"[Selenium] Page title: {page_title[:60]}")
        print(f"[Selenium] Got {len(html)} chars of HTML")

        # Debug: check for CAPTCHA or error pages
        html_lower = html.lower()
        if "captcha" in html_lower or "robot" in html_lower:
            if "productTitle" not in html and len(html) < 20000:
                print("[Selenium] ⚠ Got CAPTCHA page, retrying with longer delay...")
                time.sleep(random.uniform(5, 10))
                driver.delete_all_cookies()
                driver.get("https://www.google.com")
                time.sleep(2)
                driver.get(url)
                time.sleep(random.uniform(5, 8))
                driver.execute_script("window.scrollTo(0, 800);")
                time.sleep(2)
                html = driver.page_source
                print(f"[Selenium] Retry got {len(html)} chars")
                if "captcha" in html.lower() and "productTitle" not in html:
                    print("[Selenium] ⚠ Still CAPTCHA after retry")
                    return None

        if html and len(html) > 5000:
            print(f"[Selenium] ✅ Success! Got {len(html)} chars")
            return html
        elif html and len(html) > 2000:
            # Small page — might be an error page but let's try parsing anyway
            print(f"[Selenium] ⚠ Small page ({len(html)} chars), passing to parser...")
            return html
        print(f"[Selenium] ✗ Page too small ({len(html) if html else 0} chars)")
        return None

    except Exception as e:
        print(f"[Selenium error] {e}")
        return None
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


async def fetch_html_selenium(url: str, platform: str) -> Optional[str]:
    """Async wrapper that runs Selenium in a thread pool (non-blocking)."""
    if not SELENIUM_AVAILABLE:
        return None
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _fetch_with_selenium_sync, url, platform)


# ── STRATEGY 2: httpx session simulation (FREE) ──────────────────────────────

async def fetch_html_session(url: str, platform: str) -> Optional[str]:
    """
    Simulate a real browser session:
    1. First visit the homepage to get cookies
    2. Then visit the product page with those cookies
    """
    homepage_map = {
        "amazon": "https://www.amazon.in/",
        "flipkart": "https://www.flipkart.com/",
        "meesho": "https://www.meesho.com/",
        "myntra": "https://www.myntra.com/",
        "snapdeal": "https://www.snapdeal.com/",
        "jiomart": "https://www.jiomart.com/",
        "croma": "https://www.croma.com/",
    }

    homepage = homepage_map.get(platform, url.split("/")[0] + "//" + urlparse(url).netloc + "/")
    print(f"[Session] Step 1: Visiting homepage {homepage[:50]}...")

    headers = get_stealth_headers(referer="https://www.google.com/")

    try:
        async with httpx.AsyncClient(
            headers=headers,
            follow_redirects=True,
            timeout=25.0,
        ) as client:
            # Step 1: Get cookies from homepage
            home_resp = await client.get(homepage)
            cookies = dict(home_resp.cookies)
            print(f"[Session] Got {len(cookies)} cookies from homepage")

            # Small delay to look human
            await asyncio.sleep(random.uniform(1.0, 2.5))

            # Step 2: Visit product page with cookies + Referer
            headers["Referer"] = homepage
            product_resp = await client.get(url, headers=headers)

            if product_resp.status_code == 200 and len(product_resp.text) > 3000:
                html = product_resp.text
                if "captcha" in html.lower() and len(html) < 10000:
                    print("[Session] ⚠ Got CAPTCHA")
                    return None
                print(f"[Session] ✅ Got {len(html)} chars")
                return html
            print(f"[Session] Status {product_resp.status_code}, size {len(product_resp.text)}")
            return None
    except Exception as e:
        print(f"[Session error] {e}")
        return None


# ── STRATEGY 3: Direct httpx with stealth headers (FREE) ─────────────────────

async def fetch_html_direct(url: str) -> Optional[str]:
    """Simple direct request with stealth headers. Works best for Flipkart/Meesho."""
    headers = get_stealth_headers()
    try:
        async with httpx.AsyncClient(
            headers=headers,
            follow_redirects=True,
            timeout=25.0,
        ) as client:
            resp = await client.get(url)
            if resp.status_code == 200 and len(resp.text) > 2000:
                print(f"[Direct] ✅ Got {len(resp.text)} chars")
                return resp.text
            print(f"[Direct] Status {resp.status_code}, size {len(resp.text)}")
            return None
    except Exception as e:
        print(f"[Direct error] {e}")
        return None


# ── STRATEGY 4: Amazon mobile site (weaker bot detection, FREE) ──────────────

async def fetch_html_mobile(asin: str) -> Optional[str]:
    """
    Amazon's mobile site (m.amazon.in) has significantly weaker bot detection
    than the desktop site. Often works when desktop is blocked.
    """
    mobile_url = f"https://m.amazon.in/dp/{asin}"
    print(f"[Mobile] Trying {mobile_url}")

    mobile_uas = [
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36",
    ]

    headers = {
        "User-Agent": random.choice(mobile_uas),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.google.com/search?q=amazon",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
    }

    try:
        async with httpx.AsyncClient(
            headers=headers,
            follow_redirects=True,
            timeout=20.0,
        ) as client:
            resp = await client.get(mobile_url)
            if resp.status_code == 200 and len(resp.text) > 2000:
                print(f"[Mobile] ✅ Got {len(resp.text)} chars")
                return resp.text
            return None
    except Exception as e:
        print(f"[Mobile error] {e}")
        return None


# ─── Amazon Parser ────────────────────────────────────────────────────────────

def parse_amazon(html: str) -> dict:
    """Parse Amazon HTML with BeautifulSoup."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")

        # Title
        title = ""
        for sel in [{"id": "productTitle"}, {"id": "title"}]:
            el = soup.find(**{"attrs": sel}) if "attrs" in sel else soup.find(id=sel.get("id"))
            el = soup.find(id=list(sel.values())[0])
            if el:
                title = clean_text(el.get_text())
                break
        if not title:
            el = soup.find("h1", class_=re.compile(r"title|product", re.I))
            if el:
                title = clean_text(el.get_text())

        # Price — try many selectors
        price = None
        price_selectors = [
            ("id", "priceblock_ourprice"),
            ("id", "priceblock_dealprice"),
            ("id", "priceblock_saleprice"),
            ("id", "price_inside_buybox"),
            ("class_", "a-price-whole"),
        ]
        for attr, val in price_selectors:
            el = soup.find(**{attr: val})
            if el:
                price = clean_price(el.get_text())
                if price:
                    break

        # Try CSS selectors
        if not price:
            for sel in [
                ".apexPriceToPay .a-offscreen",
                ".priceToPay .a-offscreen",
                "#corePrice_feature_div .a-price .a-offscreen",
                "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen",
                ".a-price .a-offscreen",
            ]:
                el = soup.select_one(sel)
                if el:
                    price = clean_price(el.get_text())
                    if price:
                        break

        # MRP
        mrp = None
        for sel in [
            ".a-text-price .a-offscreen",
            "#listPrice",
            "#priceblock_listprice",
            ".basisPrice .a-offscreen",
        ]:
            el = soup.select_one(sel)
            if el:
                mrp = clean_price(el.get_text())
                if mrp and (not price or mrp > price):
                    break

        # Image
        image = ""
        img_el = soup.find("img", {"id": "landingImage"}) or soup.find("img", {"id": "imgBlkFront"})
        if img_el:
            image = img_el.get("data-old-hires") or img_el.get("src") or ""
            if not image or image.startswith("data:"):
                dyn = img_el.get("data-a-dynamic-image", "{}")
                try:
                    keys = list(json.loads(dyn).keys())
                    if keys:
                        image = keys[-1]
                except Exception:
                    pass

        # Rating
        rating = None
        rating_el = soup.find(id="acrPopover") or soup.find(attrs={"data-hook": "rating-out-of-text"})
        if rating_el:
            m = re.search(r"([\d.]+)\s*out of", rating_el.get_text(), re.I)
            if m:
                rating = float(m.group(1))

        # Review count
        reviews = None
        rev_el = soup.find(id="acrCustomerReviewText")
        if rev_el:
            m = re.search(r"([\d,]+)", rev_el.get_text())
            if m:
                reviews = int(m.group(1).replace(",", ""))

        # Availability
        avail_el = soup.find(id="availability")
        availability = "In Stock"
        if avail_el:
            t = avail_el.get_text().lower()
            if "out of stock" in t or "unavailable" in t:
                availability = "Out of Stock"

        # Discount
        discount = None
        disc_el = soup.select_one(".savingsPercentage")
        if disc_el:
            m = re.search(r"(\d+)", disc_el.get_text())
            if m:
                discount = float(m.group(1))

        return {
            "title": title or "Amazon Product",
            "current_price": price,
            "original_price": mrp,
            "image_url": image,
            "availability": availability,
            "rating": rating,
            "review_count": reviews,
            "discount_percent": discount,
            "currency": "INR",
        }

    except ImportError:
        return parse_with_regex(html, "amazon")


def parse_flipkart(html: str) -> dict:
    """Parse Flipkart HTML. Flipkart uses obfuscated class names that change
    frequently, so we use MULTIPLE selector strategies."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")

        # Title — try multiple approaches
        title = ""
        # 1. Look for <h1> with common Flipkart title classes
        for cls in ["B_NuCI", "yhB1nd", "_35KyD6", "VU-ZEz"]:
            el = soup.find(class_=cls)
            if el:
                title = clean_text(el.get_text())
                break
        # 2. Any <h1> on the page
        if not title:
            h1 = soup.find("h1")
            if h1:
                title = clean_text(h1.get_text())
        # 3. Try <span> inside breadcrumb-like containers
        if not title:
            for tag in soup.find_all("span", class_=re.compile(r"title|name|heading", re.I)):
                t = clean_text(tag.get_text())
                if len(t) > 10:
                    title = t
                    break

        # Price — Flipkart changes class names often, so cast a wide net
        price = None
        # Old class names
        for sel in ["._30jeq3._16Jk6d", "._30jeq3", "._16Jk6d", "._25b18c ._30jeq3"]:
            el = soup.select_one(sel)
            if el:
                price = clean_price(el.get_text())
                if price:
                    break
        # New class names (2025+)
        if not price:
            for sel in [".Nx9bqj._4b5DiR", ".Nx9bqj", ".CEmiEU", ".hl05eU .Nx9bqj"]:
                el = soup.select_one(sel)
                if el:
                    price = clean_price(el.get_text())
                    if price:
                        break
        # Generic: find any element with ₹ and a large number
        if not price:
            for tag in soup.find_all(["div", "span"], string=re.compile(r"₹\s*[\d,]+")):
                p = clean_price(tag.get_text())
                if p and p > 50:
                    price = p
                    break

        # MRP (original price)
        mrp = None
        for sel in ["._3I9_wc._2p6lqe", "._3I9_wc", "._3auQ3N", ".yRaY8j", ".CxhGGd"]:
            el = soup.select_one(sel)
            if el:
                mrp = clean_price(el.get_text())
                if mrp and (not price or mrp > price):
                    break

        # Discount
        discount = None
        for sel in ["._3Ay6Sb._31Dcoz span", "._3Ay6Sb span", ".VGWI6T", ".UkUFwK span"]:
            el = soup.select_one(sel)
            if el:
                m = re.search(r"(\d+)%", el.get_text())
                if m:
                    discount = float(m.group(1))
                    break

        # Image
        image = ""
        for sel in ["img._396cs4", "img._2r_T1I", "div._3kidJX img", "img.DByuf4", "img._0DkuPH"]:
            el = soup.select_one(sel)
            if el:
                image = el.get("src", "")
                break
        if not image:
            # Try og:image meta tag
            og = soup.find("meta", property="og:image")
            if og:
                image = og.get("content", "")

        # Rating
        rating = None
        for sel in ["._3LWZlK", ".XQDdHH"]:
            el = soup.select_one(sel)
            if el:
                m = re.search(r"([\d.]+)", el.get_text())
                if m:
                    rating = float(m.group(1))
                    break

        return {
            "title": title or "Flipkart Product",
            "current_price": price,
            "original_price": mrp,
            "image_url": image,
            "availability": "In Stock",
            "rating": rating,
            "review_count": None,
            "discount_percent": discount,
            "currency": "INR",
        }
    except ImportError:
        return parse_with_regex(html, "flipkart")


def parse_myntra(html: str) -> dict:
    """Parse Myntra product page (fashion e-commerce)."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")

        # Title
        title = ""
        h1 = soup.find("h1", class_=re.compile(r"productTitle|title", re.I))
        if h1:
            title = clean_text(h1.get_text())
        if not title:
            # Try any h1
            h1 = soup.find("h1")
            if h1:
                title = clean_text(h1.get_text())

        # Price — Myntra displays price in span with rupee symbol
        price = None
        for el in soup.find_all(["span", "div"], string=re.compile(r"₹|Rs\.?\s*\d")):
            p = clean_price(el.get_text())
            if p and p > 100:  # Valid product price
                price = p
                break

        # Original price (MRP)
        mrp = None
        for el in soup.find_all(["span", "div"], class_=re.compile(r"mrp|original|strikethrough", re.I)):
            m = clean_price(el.get_text())
            if m and (not price or m > price):
                mrp = m
                break

        # Discount percentage
        discount = None
        for el in soup.find_all(["span", "div"], string=re.compile(r"(\d+)%\s*off")):
            m = re.search(r"(\d+)%", el.get_text())
            if m:
                discount = float(m.group(1))
                break

        # Image
        image = ""
        img = soup.find("img", class_=re.compile(r"productImage|main-image", re.I))
        if img:
            image = img.get("src", "") or img.get("data-src", "")
        if not image:
            og = soup.find("meta", property="og:image")
            if og:
                image = og.get("content", "")

        # Rating
        rating = None
        for el in soup.find_all(["span", "div"], class_=re.compile(r"rating|stars", re.I)):
            m = re.search(r"([\d.]+)\s*(?:out of|/)\s*5", el.get_text())
            if m:
                rating = float(m.group(1))
                break

        return {
            "title": title or "Myntra Product",
            "current_price": price,
            "original_price": mrp,
            "image_url": image,
            "availability": "In Stock",
            "rating": rating,
            "review_count": None,
            "discount_percent": discount,
            "currency": "INR",
        }
    except ImportError:
        return parse_with_regex(html, "myntra")


def parse_snapdeal(html: str) -> dict:
    """Parse Snapdeal product page (general e-commerce)."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")

        # Title — try multiple selectors
        title = ""
        for sel in [".pdpHeading", ".prodTitle", "h1.product-title", "h1"]:
            el = soup.select_one(sel)
            if el:
                title = clean_text(el.get_text())
                if len(title) > 5:
                    break

        # Price — Snapdeal shows selling price in bold
        price = None
        for sel in [".sellingPrice", ".discountedPrice", ".productPrice", "span[itemprop='price']"]:
            el = soup.select_one(sel)
            if el:
                price = clean_price(el.get_text())
                if price:
                    break

        # Original price (MRP)
        mrp = None
        for sel in [".mrpPrice", ".originalPrice", ".strikethrough"]:
            el = soup.select_one(sel)
            if el:
                mrp = clean_price(el.get_text())
                if mrp and (not price or mrp > price):
                    break

        # Discount
        discount = None
        for el in soup.find_all(["span", "div"], string=re.compile(r"(\d+)%\s*off")):
            m = re.search(r"(\d+)%", el.get_text())
            if m:
                discount = float(m.group(1))
                break

        # Image
        image = ""
        img = soup.find("img", class_=re.compile(r"productImage|mainImage", re.I))
        if img:
            image = img.get("src", "") or img.get("data-src", "")
        if not image:
            og = soup.find("meta", property="og:image")
            if og:
                image = og.get("content", "")

        # Rating
        rating = None
        rating_el = soup.find("span", class_=re.compile(r"rating|stars", re.I))
        if rating_el:
            m = re.search(r"([\d.]+)", rating_el.get_text())
            if m:
                rating = float(m.group(1))

        # Availability
        availability = "In Stock"
        oos = soup.find(string=re.compile(r"out of stock|unavailable", re.I))
        if oos:
            availability = "Out of Stock"

        return {
            "title": title or "Snapdeal Product",
            "current_price": price,
            "original_price": mrp,
            "image_url": image,
            "availability": availability,
            "rating": rating,
            "review_count": None,
            "discount_percent": discount,
            "currency": "INR",
        }
    except ImportError:
        return parse_with_regex(html, "snapdeal")


def parse_generic_jsonld(html: str, platform: str) -> dict:
    """Extract from JSON-LD structured data."""
    for match in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.DOTALL):
        try:
            d = json.loads(match.group(1))
            if isinstance(d, list):
                d = d[0]
            if d.get("@type") in ("Product", "ItemPage"):
                offers = d.get("offers", {})
                if isinstance(offers, list):
                    offers = offers[0]
                price = clean_price(offers.get("price") or offers.get("lowPrice"))
                if not price:
                    continue
                img = d.get("image", "")
                if isinstance(img, list): img = img[0]
                if isinstance(img, dict): img = img.get("url", "")
                return {
                    "title": clean_text(d.get("name", f"{platform.title()} Product")),
                    "current_price": price,
                    "original_price": None,
                    "image_url": str(img),
                    "availability": "In Stock",
                    "rating": None,
                    "review_count": None,
                    "discount_percent": None,
                    "currency": "INR",
                }
        except Exception:
            continue
    return {}


def parse_with_regex(html: str, platform: str) -> dict:
    """Last resort: regex extraction from raw HTML."""
    price = None
    for pattern in [
        r'"price":\s*"?(\d[\d,]*(?:\.\d{1,2})?)"?',
        r'₹\s*([\d,]+)',
        r'"selling_price":\s*"?(\d+)"?',
        r'"finalPrice":\s*(\d+)',
        r'"discounted_price":\s*(\d+)',
        r'data-price="(\d[\d,]*)"',
        r'"mrp":\s*(\d+)',
        r'"sp":\s*(\d+)',
    ]:
        m = re.search(pattern, html)
        if m:
            p = clean_price(m.group(1))
            if p and p > 10:
                price = p
                break

    title_m = re.search(r'<title[^>]*>([^<]+)</title>', html)
    title = clean_text(title_m.group(1)) if title_m else f"{platform.title()} Product"

    og_img = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html)
    image = og_img.group(1) if og_img else ""

    return {
        "title": title[:200],
        "current_price": price,
        "original_price": None,
        "image_url": image,
        "availability": "In Stock",
        "rating": None,
        "review_count": None,
        "discount_percent": None,
        "currency": "INR",
    }


# ─── Main Scraper ─────────────────────────────────────────────────────────────

async def scrape_product(url: str, platform: str) -> dict:
    """
    Multi-strategy scraping pipeline — ALL FREE, uses Selenium + BeautifulSoup:
      1. Selenium + undetected-chromedriver (most reliable — runs REAL Chrome)
      2. httpx session simulation (visit homepage first for cookies, then product)
      3. Amazon mobile site (m.amazon.in has weaker bot detection)
      4. Direct httpx request with stealth headers (last resort)
    """
    print(f"\n{'='*60}")
    print(f"[Scraping] {platform}: {url[:80]}")
    print(f"{'='*60}")

    html = None

    # ── STRATEGY 1: Selenium + undetected-chromedriver (BEST) ────────────────
    if SELENIUM_AVAILABLE:
        print("[Strategy 1] Selenium + undetected-chromedriver (stealth Chrome)...")
        clean_url = url
        if platform == "amazon":
            asin = extract_asin(url)
            if asin:
                clean_url = f"https://www.amazon.in/dp/{asin}?th=1&psc=1"
        html = await fetch_html_selenium(clean_url, platform)
        if html:
            print(f"[Strategy 1] ✅ Got HTML ({len(html)} chars)")
    else:
        print("[Strategy 1] Skipped — Selenium not installed")
        print("             Install with: pip install selenium undetected-chromedriver")

    # ── STRATEGY 2: httpx session simulation (homepage → product) ────────────
    if not html:
        print("[Strategy 2] httpx session simulation...")
        html = await fetch_html_session(url, platform)

    # ── STRATEGY 3: Amazon mobile site ───────────────────────────────────────
    if not html and platform == "amazon":
        asin = extract_asin(url)
        if asin:
            print("[Strategy 3] Amazon mobile site (m.amazon.in)...")
            html = await fetch_html_mobile(asin)

    # ── STRATEGY 4: Direct request with stealth headers ──────────────────────
    if not html:
        print("[Strategy 4] Direct httpx request...")
        clean_url = url
        if platform == "amazon":
            asin = extract_asin(url)
            if asin:
                clean_url = f"https://www.amazon.in/dp/{asin}?th=1&psc=1"
        html = await fetch_html_direct(clean_url)

    if not html or len(html) < 1000:
        strategies_tried = []
        if SELENIUM_AVAILABLE:
            strategies_tried.append("Selenium + undetected-chromedriver")
        strategies_tried.extend(["Session simulation", "Direct request"])
        if platform == "amazon":
            strategies_tried.append("Mobile site")

        raise HTTPException(
            status_code=503,
            detail=(
                f"Could not load the product page after trying: {', '.join(strategies_tried)}.\n\n"
                "RECOMMENDED FIX (free, no API keys):\n\n"
                "Install Selenium + undetected-chromedriver:\n"
                "  pip install selenium undetected-chromedriver\n\n"
                "Make sure Google Chrome is installed on your system.\n\n"
                "If it still fails, the site might be temporarily rate-limiting. "
                "Try again in a few minutes."
            )
        )

    # ── Parse HTML with BeautifulSoup ────────────────────────────────────────
    print(f"[Parsing] HTML size: {len(html)} chars")

    result = {}

    if platform == "amazon":
        result = parse_amazon(html)
    elif platform == "flipkart":
        result = parse_flipkart(html)
    elif platform == "myntra":
        result = parse_myntra(html)
    elif platform == "snapdeal":
        result = parse_snapdeal(html)
    else:
        result = parse_generic_jsonld(html, platform)
        if not result.get("current_price"):
            result = parse_with_regex(html, platform)

    # Fallback: JSON-LD structured data
    if not result.get("current_price"):
        print("[Fallback] Trying JSON-LD...")
        fallback = parse_generic_jsonld(html, platform)
        if fallback.get("current_price"):
            result = fallback

    # Fallback: Regex
    if not result.get("current_price"):
        print("[Fallback] Trying regex...")
        fallback = parse_with_regex(html, platform)
        if fallback.get("current_price"):
            result.update(fallback)

    print(f"[Result] Price: {result.get('current_price')}, Title: {str(result.get('title',''))[:50]}")

    if not result.get("current_price"):
        raise HTTPException(
            status_code=422,
            detail=(
                "Got the page HTML but couldn't extract the price.\n\n"
                "This usually means the site returned a CAPTCHA or login wall.\n\n"
                "FIX: Make sure undetected-chromedriver is installed:\n"
                "  pip install selenium undetected-chromedriver\n\n"
                "It patches Chrome to bypass bot detection."
            )
        )

    return result


# ─── API Endpoints ────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "name": "Smart Price Tracker API",
        "version": "7.0.0",
        "all_free": True,
        "strategies": {
            "selenium_undetected": "available ✅" if SELENIUM_AVAILABLE else "not installed — run: pip install selenium undetected-chromedriver",
            "beautifulsoup": "available ✅" if BS4_AVAILABLE else "not installed — run: pip install beautifulsoup4 lxml",
            "session_simulation": "available ✅",
            "mobile_site": "available ✅ (Amazon)",
            "direct_request": "available ✅",
        },
        "tip": "Uses Selenium + undetected-chromedriver + BeautifulSoup. 100% free, no API keys!"
    }

@app.get("/api/health")
async def health():
    return {
        "status": "healthy",
        "strategies": {
            "selenium_undetected": SELENIUM_AVAILABLE,
            "beautifulsoup": BS4_AVAILABLE,
            "session_simulation": True,
            "mobile_site": True,
            "direct_httpx": True,
        },
        "all_free": True,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/fetch-product", response_model=ProductResponse)
async def fetch_product(request: ProductRequest):
    url = request.url.strip()

    if not validate_url(url):
        raise HTTPException(status_code=400, detail="Invalid URL. Please provide a valid https:// product URL.")

    platform = detect_platform(url)
    scraped = await scrape_product(url, platform)

    current_price = scraped.get("current_price")
    if not current_price or current_price <= 0:
        raise HTTPException(status_code=422, detail="Could not extract a valid price.")

    original_price = scraped.get("original_price")
    discount_percent = scraped.get("discount_percent")
    if not discount_percent and original_price and original_price > current_price:
        discount_percent = round(((original_price - current_price) / original_price) * 100, 1)

    image_url = scraped.get("image_url") or ""
    if not image_url or image_url.startswith("data:"):
        image_url = "https://placehold.co/300x300/0d1526/475569?text=No+Image"

    seller_verified = platform in ["amazon", "flipkart", "myntra", "meesho", "snapdeal", "jiomart", "croma", "tatacliq"]
    if discount_percent and discount_percent > 80:
        seller_verified = False

    # ── Auto-compare: search other platforms for the same product ─────────
    title = scraped.get("title", "")
    comparison = []
    if title and len(title) > 3:
        comparison = await _compare_on_other_platforms(title, platform)
        print(f"[Compare] Found {len(comparison)} results from other platforms")

    # ── Save price to history database ────────────────────────────────────
    _save_price_point(url, platform, title, current_price, original_price)

    # ── Retrieve history for this URL ─────────────────────────────────────
    history = _get_price_history(url)

    return ProductResponse(
        platform=platform,
        title=title,
        current_price=current_price,
        currency="INR",
        original_price=original_price,
        discount_percent=discount_percent,
        image_url=image_url,
        availability=scraped.get("availability", "In Stock"),
        rating=scraped.get("rating"),
        review_count=scraped.get("review_count"),
        seller_verified=seller_verified,
        scraped_at=datetime.now().isoformat(),
        comparison=comparison,
        price_history=history,
    )

@app.get("/api/price-history")
async def get_price_history(url: str):
    """Get all saved price history for a product URL."""
    if not url or not validate_url(url):
        raise HTTPException(status_code=400, detail="Invalid URL.")
    history = _get_price_history(url)
    return {
        "url": url,
        "data_points": len(history),
        "history": history,
    }

@app.get("/api/platforms")
async def platforms():
    return {"supported": list(PLATFORM_PATTERNS.keys())}

# ─── Price Watch Endpoints ────────────────────────────────────────────────────

@app.post("/api/watches")
async def create_watch(request: WatchRequest):
    """Create a new price watch for a product."""
    if not validate_url(request.url):
        raise HTTPException(status_code=400, detail="Invalid URL.")
    
    if request.target_price <= 0:
        raise HTTPException(status_code=400, detail="Target price must be positive.")
    
    if not request.email or "@" not in request.email:
        raise HTTPException(status_code=400, detail="Valid email required.")
    
    platform = detect_platform(request.url)
    
    # Try to get product title from a quick scrape
    try:
        scraped = await scrape_product(request.url, platform)
        title = scraped.get("title", "Unknown Product")
    except:
        title = "Product"
    
    success = _create_watch(request.url, request.target_price, request.email, title, platform)
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to create watch.")
    
    return {
        "status": "created",
        "message": f"Watch created. You'll be notified when price reaches ₹{request.target_price:,.0f}",
        "url": request.url,
        "target_price": request.target_price,
        "email": request.email,
    }

@app.get("/api/watches")
async def list_watches():
    """Get all price watches (active and triggered)."""
    watches = _list_watches()
    return {
        "total": len(watches),
        "active": len([w for w in watches if w.get("active") == 1]),
        "triggered": len([w for w in watches if w.get("active") == 0 and w.get("triggered_at")]),
        "watches": watches,
    }

@app.delete("/api/watches/{watch_id}")
async def delete_watch(watch_id: int):
    """Delete a price watch by ID."""
    success = _delete_watch(watch_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Watch not found.")
    
    return {
        "status": "deleted",
        "message": f"Watch #{watch_id} deleted.",
    }


# ─── Cross-Platform Price Comparison ──────────────────────────────────────────

def _build_search_urls(query: str) -> dict:
    """Build search URLs for each platform given a product title."""
    q = quote_plus(query[:80])  # Truncate long titles
    return {
        "amazon":   f"https://www.amazon.in/s?k={q}",
        "flipkart": f"https://www.flipkart.com/search?q={q}",
        "myntra":   f"https://www.myntra.com/search?q={q}",
        "snapdeal": f"https://www.snapdeal.com/search?keyword={q}",
    }


def _parse_amazon_search(html: str) -> Optional[dict]:
    """Parse Amazon search results page to get the first real product."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")

        # Each search result is in a div with data-component-type="s-search-result"
        results = soup.select('[data-component-type="s-search-result"]')
        if not results:
            # Fallback: try finding result cards
            results = soup.select('.s-result-item[data-asin]')

        for result in results[:5]:  # Check first 5 results
            asin = result.get("data-asin", "")
            if not asin or len(asin) != 10:
                continue

            # Skip sponsored/ad results
            if result.select_one('.puis-label-popover-default, [data-component-type="sp-sponsored-result"]'):
                continue

            # Title
            title_el = result.select_one('h2 a span, h2 span.a-text-normal')
            title = clean_text(title_el.get_text()) if title_el else ""
            if not title or len(title) < 5:
                continue

            # Price
            price = None
            for sel in ['.a-price .a-offscreen', '.a-price-whole', '.a-color-price']:
                el = result.select_one(sel)
                if el:
                    price = clean_price(el.get_text())
                    if price:
                        break
            if not price:
                continue

            # Image
            img_el = result.select_one('img.s-image')
            image = img_el.get("src", "") if img_el else ""

            # Rating
            rating = None
            rating_el = result.select_one('.a-icon-alt')
            if rating_el:
                m = re.search(r'([\d.]+)\s*out', rating_el.get_text())
                if m:
                    rating = float(m.group(1))

            # Product URL
            link_el = result.select_one('h2 a')
            product_url = ""
            if link_el:
                href = link_el.get("href", "")
                if href.startswith("/"):
                    product_url = f"https://www.amazon.in{href}"
                elif href.startswith("http"):
                    product_url = href

            return {
                "platform": "amazon",
                "title": title[:150],
                "price": price,
                "image_url": image,
                "product_url": product_url,
                "rating": rating,
            }
    except Exception as e:
        print(f"[Amazon Search Parse Error] {e}")
    return None


def _parse_flipkart_search(html: str) -> Optional[dict]:
    """Parse Flipkart search results page to get the first real product."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")

        # Flipkart search result containers — class names change frequently
        # Try multiple strategies
        results = soup.select('div[data-id]')
        if not results:
            results = soup.select('._1AtVbE, ._75nlfW, .cPHDOP')
        if not results:
            # Try any link that leads to a product page
            results = soup.select('a[href*="/p/"]')

        for result in results[:8]:
            # Title
            title = ""
            for sel in ['.IRpwTa', '.s1Q9rs', '._4rR01T', '.WKTcLC', 'a[title]', '.Xpx9i']:
                el = result.select_one(sel)
                if el:
                    title = clean_text(el.get("title") or el.get_text())
                    if len(title) > 5:
                        break

            if not title or len(title) < 5:
                # Try getting title from any reasonable text element
                for tag in result.find_all(['a', 'div'], class_=True):
                    t = clean_text(tag.get_text())
                    if 10 < len(t) < 200 and not t.startswith("₹"):
                        title = t
                        break
            if not title or len(title) < 5:
                continue

            # Price
            price = None
            for sel in ['._30jeq3', '.Nx9bqj', '._1_WHN1', '.hl05eU .Nx9bqj']:
                el = result.select_one(sel)
                if el:
                    price = clean_price(el.get_text())
                    if price:
                        break
            if not price:
                # Try finding any ₹ value
                for tag in result.find_all(['div', 'span'], string=re.compile(r'₹')):
                    p = clean_price(tag.get_text())
                    if p and p > 50:
                        price = p
                        break
            if not price:
                continue

            # Image
            image = ""
            img_el = result.select_one('img._396cs4, img._2r_T1I, img.DByuf4, img._0DkuPH')
            if img_el:
                image = img_el.get("src", "")
            if not image:
                img_el = result.select_one('img[src*="img.fkcdn"]')
                if img_el:
                    image = img_el.get("src", "")

            # Rating
            rating = None
            for sel in ['._3LWZlK', '.XQDdHH']:
                el = result.select_one(sel)
                if el:
                    m = re.search(r'([\d.]+)', el.get_text())
                    if m:
                        rating = float(m.group(1))
                        break

            # Product URL
            product_url = ""
            link_el = result.select_one('a[href*="/p/"]') or result if result.name == 'a' else None
            if link_el:
                href = link_el.get("href", "")
                if href.startswith("/"):
                    product_url = f"https://www.flipkart.com{href}"
                elif href.startswith("http"):
                    product_url = href

            return {
                "platform": "flipkart",
                "title": title[:150],
                "price": price,
                "image_url": image,
                "product_url": product_url,
                "rating": rating,
            }
    except Exception as e:
        print(f"[Flipkart Search Parse Error] {e}")
    return None


def _parse_myntra_search(html: str) -> Optional[dict]:
    """Parse Myntra search results page to get the first real product."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")

        # Myntra search result containers
        results = soup.select('li[data-productid], .productCardImg')
        if not results:
            results = soup.select('.productContainer, .productCardImg')

        for result in results[:8]:
            # Title — usually in productBrand or productName
            title = ""
            for sel in ['.productBrand', '.productName', '.brand', 'h3, h4']:
                el = result.select_one(sel)
                if el:
                    title = clean_text(el.get_text())
                    if len(title) > 3:
                        break
            if not title or len(title) < 3:
                continue

            # Price
            price = None
            for sel in ['.productPrice, .discountedPriceText', '.discountedPrice', '.newPrice']:
                el = result.select_one(sel)
                if el:
                    price = clean_price(el.get_text())
                    if price:
                        break
            if not price:
                continue

            # Image
            image = ""
            img_el = result.select_one('img[src*="images.myntra"]')
            if img_el:
                image = img_el.get("src", "")

            # Rating
            rating = None
            for sel in ['.productRating', '.ratingNumber']:
                el = result.select_one(sel)
                if el:
                    m = re.search(r'([\d.]+)', el.get_text())
                    if m:
                        rating = float(m.group(1))
                        break

            # Product URL
            product_url = ""
            link_el = result.select_one('a[href*="/p/"]') or result.find_parent('a')
            if link_el and link_el.name == 'a':
                href = link_el.get("href", "")
                if href.startswith("/"):
                    product_url = f"https://www.myntra.com{href}"
                elif href.startswith("http"):
                    product_url = href

            return {
                "platform": "myntra",
                "title": title[:150],
                "price": price,
                "image_url": image,
                "product_url": product_url,
                "rating": rating,
            }
    except Exception as e:
        print(f"[Myntra Search Parse Error] {e}")
    return None


def _parse_snapdeal_search(html: str) -> Optional[dict]:
    """Parse Snapdeal search results page to get the first real product."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")

        # Snapdeal search result containers
        results = soup.select('div.productCardImg, .productContainer')
        if not results:
            results = soup.select('[data-productid], .productCard')

        for result in results[:8]:
            # Title
            title = ""
            for sel in ['.productTitle', '.productName', '.prdName', 'h2, h3']:
                el = result.select_one(sel)
                if el:
                    title = clean_text(el.get_text())
                    if len(title) > 3:
                        break
            if not title or len(title) < 3:
                continue

            # Price
            price = None
            for sel in ['.productPrice, .discountedPrice', '.newPrice', '.rsPriceTag']:
                el = result.select_one(sel)
                if el:
                    price = clean_price(el.get_text())
                    if price:
                        break
            if not price:
                continue

            # Image
            image = ""
            img_el = result.select_one('img[src*="snapdeal"]')
            if img_el:
                image = img_el.get("src", "")

            # Rating
            rating = None
            for sel in ['.productRating', '.ratingNumber, .reviewCount']:
                el = result.select_one(sel)
                if el:
                    m = re.search(r'([\d.]+)', el.get_text())
                    if m:
                        rating = float(m.group(1))
                        break

            # Product URL
            product_url = ""
            link_el = result.select_one('a[href*="/product/"]') or result.find_parent('a')
            if link_el and link_el.name == 'a':
                href = link_el.get("href", "")
                if href.startswith("/"):
                    product_url = f"https://www.snapdeal.com{href}"
                elif href.startswith("http"):
                    product_url = href

            return {
                "platform": "snapdeal",
                "title": title[:150],
                "price": price,
                "image_url": image,
                "product_url": product_url,
                "rating": rating,
            }
    except Exception as e:
        print(f"[Snapdeal Search Parse Error] {e}")
    return None


async def _scrape_search_page(platform: str, search_url: str) -> Optional[dict]:
    """Scrape a search results page for the top result."""
    print(f"\n[Compare] Searching {platform}: {search_url[:80]}...")

    html = None

    # Try Selenium first (most reliable)
    if SELENIUM_AVAILABLE:
        html = await fetch_html_selenium(search_url, platform)

    # Fallback to session simulation
    if not html:
        html = await fetch_html_session(search_url, platform)

    # Fallback to direct request
    if not html:
        html = await fetch_html_direct(search_url)

    if not html or len(html) < 1000:
        print(f"[Compare] ✗ Could not fetch {platform} search page")
        return None

    print(f"[Compare] Got {len(html)} chars from {platform} search")

    # Parse search results
    if platform == "amazon":
        return _parse_amazon_search(html)
    elif platform == "flipkart":
        return _parse_flipkart_search(html)
    elif platform == "myntra":
        return _parse_myntra_search(html)
    elif platform == "snapdeal":
        return _parse_snapdeal_search(html)

    return None


async def _compare_on_other_platforms(title: str, current_platform: str) -> list:
    """
    Automatically search for the product on other platforms and return real prices.
    Called internally by fetch_product — no separate API call needed.
    """
    # Simplify title for better search results
    search_query = re.sub(r'\([^)]*\)', '', title)  # Remove parenthetical info
    search_query = re.sub(r'\s+', ' ', search_query).strip()
    words = search_query.split()[:8]
    search_query = ' '.join(words)
    print(f"[Compare] Searching other platforms for: {search_query[:60]}")

    search_urls = _build_search_urls(search_query)
    results = []

    # Skip the platform the user already scraped
    platforms_to_search = {
        p: url for p, url in search_urls.items()
        if p != current_platform
    }

    # Scrape each platform sequentially
    for plat, search_url in platforms_to_search.items():
        try:
            result = await _scrape_search_page(plat, search_url)
            if result:
                results.append(result)
                print(f"[Compare] ✅ {plat}: {result['title'][:40]} — ₹{result['price']}")
            else:
                print(f"[Compare] ✗ {plat}: No results found")
        except Exception as e:
            print(f"[Compare] ✗ {plat} error: {e}")

    return results


# ─── Email Notifier ──────────────────────────────────────────────────────────
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def _send_email_notification(to_email: str, product_title: str, target_price: float, current_price: float, product_url: str):
    """Send email notification when a watch target is reached."""
    try:
        # Get SMTP config from environment or use defaults
        smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", 587))
        sender_email = os.getenv("SMTP_EMAIL", "pricetracker.notify@gmail.com")
        sender_password = os.getenv("SMTP_PASSWORD", "")
        
        # Skip if password not set
        if not sender_password:
            print(f"[Email] SMTP_PASSWORD not set. Skipping email to {to_email}")
            return False
        
        # Compose email
        subject = f"🎉 Price Alert! {product_title[:50]} reached ₹{current_price}"
        body = f"""
<html>
<body style="font-family: Arial, sans-serif; color: #333;">
  <div style="max-width: 600px; margin: 0 auto; padding: 20px; background: #f5f5f5; border-radius: 10px;">
    <h2 style="color: #14b8a6;">🎉 Price Target Reached!</h2>
    
    <p>Great news! The product you were watching has reached your target price.</p>
    
    <div style="background: white; padding: 20px; border-radius: 8px; margin: 20px 0;">
      <h3 style="margin: 0 0 10px 0;">{product_title[:100]}</h3>
      
      <table style="width: 100%; margin: 20px 0;">
        <tr style="border-bottom: 1px solid #eee;">
          <td style="padding: 10px 0;"><strong>Current Price:</strong></td>
          <td style="padding: 10px 0; text-align: right; color: #34d399; font-size: 20px; font-weight: bold;">₹{current_price:,.0f}</td>
        </tr>
        <tr>
          <td style="padding: 10px 0;"><strong>Your Target Price:</strong></td>
          <td style="padding: 10px 0; text-align: right;">₹{target_price:,.0f}</td>
        </tr>
        <tr>
          <td style="padding: 10px 0;"><strong>You Save:</strong></td>
          <td style="padding: 10px 0; text-align: right; color: #34d399;">₹{target_price - current_price:,.0f}</td>
        </tr>
      </table>
      
      <a href="{product_url}" style="display: inline-block; padding: 12px 24px; background: #14b8a6; color: white; text-decoration: none; border-radius: 6px; font-weight: bold; margin-top: 10px;">
        View Product →
      </a>
    </div>
    
    <p style="color: #666; font-size: 12px; margin-top: 20px;">
      This is an automatic notification from PriceTracker. This watch is now inactive.
    </p>
  </div>
</body>
</html>
"""
        
        # Send email
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = to_email
        msg.attach(MIMEText(body, "html"))
        
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, to_email, msg.as_string())
        server.quit()
        
        print(f"[Email] ✅ Sent notification to {to_email}")
        return True
    except Exception as e:
        print(f"[Email] ❌ Error sending email to {to_email}: {e}")
        return False


# ─── Background Watch Checker ────────────────────────────────────────────────
import asyncio
from typing import Coroutine

async def _check_watches_background():
    """Background task: check all active watches and notify if target price is reached."""
    print("[Watch] Starting background watch checker...")
    
    while True:
        try:
            # Sleep for 24 hours (86400 seconds) between checks
            check_interval = int(os.getenv("WATCH_CHECK_INTERVAL_HOURS", 24)) * 3600
            
            watches = _list_watches()
            active_watches = [w for w in watches if w.get("active") == 1]
            
            if not active_watches:
                print(f"[Watch] No active watches. Next check in {check_interval // 3600} hours.")
                await asyncio.sleep(check_interval)
                continue
            
            print(f"[Watch] Checking {len(active_watches)} active watches...")
            
            for watch in active_watches:
                watch_id = watch.get("id")
                url = watch.get("url")
                target_price = watch.get("target_price")
                email = watch.get("email")
                product_title = watch.get("title", "Product")
                
                try:
                    print(f"[Watch] Checking watch #{watch_id}: {url} <= ₹{target_price}")
                    
                    # Scrape current price
                    platform = detect_platform(url)
                    scraped = await scrape_product(url, platform)
                    current_price = scraped.get("current_price")
                    
                    if not current_price:
                        print(f"[Watch] Could not scrape price for watch #{watch_id}")
                        continue
                    
                    # Update last_checked
                    conn = sqlite3.connect(DB_PATH)
                    conn.execute(
                        "UPDATE watches SET last_checked = ? WHERE id = ?",
                        (datetime.now().isoformat(), watch_id)
                    )
                    conn.commit()
                    conn.close()
                    
                    # Check if target reached
                    if current_price <= target_price:
                        print(f"[Watch] ✅ Target reached! Watch #{watch_id}: ₹{current_price} <= ₹{target_price}")
                        
                        # Send email
                        _send_email_notification(email, product_title, target_price, current_price, url)
                        
                        # Mark watch as triggered
                        conn = sqlite3.connect(DB_PATH)
                        conn.execute(
                            "UPDATE watches SET active = 0, triggered_at = ? WHERE id = ?",
                            (datetime.now().isoformat(), watch_id)
                        )
                        conn.commit()
                        conn.close()
                        print(f"[Watch] Deactivated watch #{watch_id}")
                    else:
                        print(f"[Watch] Price not yet at target. Current: ₹{current_price}, Target: ₹{target_price}")
                
                except Exception as e:
                    print(f"[Watch] Error checking watch #{watch_id}: {e}")
            
            print(f"[Watch] Watch check complete. Next check in {check_interval // 3600} hours.")
            await asyncio.sleep(check_interval)
        
        except Exception as e:
            print(f"[Watch] Error in background task: {e}")
            await asyncio.sleep(60)  # Retry after 60 seconds on error


# ─── Startup Event ───────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    """Start the background watch checker when the app starts."""
    asyncio.create_task(_check_watches_background())
    print("[Watch] Background watch checker started")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)