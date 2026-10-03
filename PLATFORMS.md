# 🛒 Price Tracker — Multi-Platform Support

## ✅ What's New

The Price Tracker now supports **4 major e-commerce platforms** with real-time price scraping, historical tracking, and cross-platform comparison:

### Supported Platforms
- **Amazon.in** — Electronics, books, general merchandise
- **Flipkart** — Electronics, fashion, home & kitchen
- **Myntra** — Fashion, clothing, accessories
- **Snapdeal** — General e-commerce, deals & discounts

## 🏗️ Architecture

### Backend (`backend/main.py`)
Each platform has dedicated parsing logic:

| Platform | Product Parser | Search Parser | Features |
|----------|---------------|---------------|----------|
| Amazon | `parse_amazon()` | `_parse_amazon_search()` | ASIN detection, sponsored filter, mobile fallback |
| Flipkart | `parse_flipkart()` | `_parse_flipkart_search()` | Product cards, multiple selector fallbacks |
| Myntra | `parse_myntra()` | `_parse_myntra_search()` | Strikethrough price (MRP), discount %, fashion-focused |
| Snapdeal | `parse_snapdeal()` | `_parse_snapdeal_search()` | Out-of-stock detection, general commerce |

### Frontend (`frontend/src/PriceTracker.jsx`)
UI reflects all 4 platforms:
- Platform badges with brand colors
- Input placeholder mentions all 4 platforms
- Comparison automatically includes all available platforms

## 🔧 How It Works

### 1. **Product Scraping**
```
User pastes URL → Platform detection → HTML fetch → Platform-specific parser → Price + details
```

Multi-strategy fetch (Selenium → Session → Direct) ensures reliability across platforms.

### 2. **Cross-Platform Comparison**
```
Product title extracted → Build search URLs for all platforms → Scrape search pages → Compare prices
```

Comparison results shown alongside product details with price difference highlights.

### 3. **Price History**
```
SQLite database stores each price check → Recharts visualizes price trends over time
```

### 4. **Price Watches**
```
User sets target price & email → Daily background check → Email notification when target reached
```

## 📋 API Endpoints

All endpoints work with any supported platform:

```bash
# Fetch product details
POST /api/fetch-product
{
  "url": "https://www.myntra.com/p/shirt/12345",
  "comparison": true
}

# Get price history
GET /api/price-history?url=...

# Manage price watches
POST   /api/watches           # Create watch
GET    /api/watches           # List watches
DELETE /api/watches/{watch_id}  # Delete watch

# Get supported platforms
GET /api/platforms

# Health check
GET /api/health
```

## 🧪 Testing

Run the platform support test:
```bash
cd backend
python test_platforms.py
```

Expected output:
```
✅ Search URLs built: amazon, flipkart, myntra, snapdeal
✅ Platform Detection: Myntra and Snapdeal detected correctly
✅ New Functions: All parser functions exist and callable
✅ All tests passed!
```

## 🚀 Running Locally

### Backend
```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev  # Runs on http://localhost:5174
```

## 📊 Example Usage

1. **Product Scraping**: Paste `https://www.myntra.com/p/tshirt/1234567890`
   - Extracts: Title, Price, MRP, Discount %, Image, Rating
   - Compares across: Amazon, Flipkart, Snapdeal

2. **Price Watch**: Set target ₹500 for a shirt
   - Daily automatic check
   - Email notification when price drops to ₹500

3. **Price History**: View price graph over last 30 days
   - Real data from actual scrapes
   - Visual price trends

## 🔍 Technical Details

### Platform Detection
Regex patterns identify platforms from URLs:
- `amazon.in/` → amazon
- `flipkart.com/` → flipkart
- `myntra.com/` → myntra
- `snapdeal.com/` → snapdeal

### Parser Fallback Strategy
Each platform tries multiple CSS selectors:
1. Primary selectors (most common class names)
2. Alternative selectors (fallback classes)
3. Generic JSON-LD structured data
4. Regex extraction as last resort

### Error Handling
- Missing price → Returns null, triggers fallback
- Missing image → Uses placeholder
- Parse error → Detailed logging, graceful fallback

## 🛠️ Adding New Platforms

To add a new platform (e.g., `eBay`):

1. **Create product parser** in `main.py`:
```python
def parse_ebay(html: str) -> dict:
    # Extract title, price, image, rating, etc.
    return {
        "title": "...",
        "current_price": 999,
        "image_url": "...",
        "rating": 4.5
    }
```

2. **Create search parser**:
```python
def _parse_ebay_search(html: str) -> Optional[dict]:
    # Parse search results, return first product
    return { ... }
```

3. **Update routing** in `scrape_product()`:
```python
elif platform == "ebay":
    result = parse_ebay(html)
```

4. **Update search URLs** in `_build_search_urls()`:
```python
return {
    ...
    "ebay": f"https://www.ebay.com/sch/i.html?_nkw={q}",
}
```

5. **Update search parser selector** in `_scrape_search_page()`:
```python
elif platform == "ebay":
    return _parse_ebay_search(html)
```

6. **Update UI** in `PriceTracker.jsx`:
- Add color to `PLATFORM_COLORS`
- Update subtitle and placeholder

## 📈 Recent Changes

### Commits
- `Add Myntra and Snapdeal platform support with product and search parsers`
  - Added `parse_myntra()` and `parse_snapdeal()` product parsers
  - Added `_parse_myntra_search()` and `_parse_snapdeal_search()` search parsers
  - Updated platform routing in main scraping logic
  - Extended search URL builder

- `Update UI to reflect Myntra and Snapdeal support`
  - Updated header subtitle
  - Added platforms to example list
  - Updated input placeholder and helper text

## 🎯 Next Steps (Optional)

Potential improvements:
- [ ] Add more platforms (Meesho, JioMart, Croma, Tata CLiQ)
- [ ] Implement price prediction using historical data
- [ ] Add category-specific parsers for better accuracy
- [ ] Support product images in email notifications
- [ ] Implement bulk URL scraping
- [ ] Add dark mode (already have colors!)
- [ ] Deploy on cloud (Vercel/AWS/Render)
- [ ] Add browser extension for quick price checks

## 📞 Support

If a platform's HTML structure changes:
1. Inspect the website in browser (F12)
2. Find new CSS class names for price/title/image
3. Update the parser selectors
4. Test with `test_platforms.py`

All parsers have multiple fallback selectors to handle minor HTML changes automatically.

---

**Last Updated**: December 2024  
**Platforms**: 4 major e-commerce sites  
**Status**: Production-ready ✅
