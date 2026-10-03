# 🛒 Stitch MCP Server for Price Tracker

A Model Context Protocol (MCP) server that enables AI assistants and automated tools to interact with the Price Tracker API for real-time e-commerce price scraping, comparison, and monitoring.

## 🎯 Purpose

Stitch MCP acts as a bridge between AI assistants (like Claude, ChatGPT, Copilot) and the Price Tracker backend. It provides standardized tools for:

- **Real-time price scraping** from 4 major e-commerce platforms
- **Cross-platform price comparison** to find the best deals
- **Historical price tracking** with trend analysis
- **Automated price watches** with email notifications
- **Product research** and market analysis

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd mcp-server
pip install -r requirements.txt
```

### 2. Configure Environment

Edit `.env` to set your Price Tracker API endpoint:

```bash
PRICE_TRACKER_API=http://localhost:8000
MCP_PORT=3001
```

### 3. Start the MCP Server

```bash
python server.py
```

Expected output:
```
╔════════════════════════════════════════════════════════════════╗
║           🛒 Price Tracker MCP Server Starting                 ║
╚════════════════════════════════════════════════════════════════╝

✨ Available Tools:
  1. fetch_product - Get product details and compare prices
  2. get_price_history - View historical price data
  3. create_price_watch - Set up price alerts
  4. list_price_watches - View all active watches
  5. delete_price_watch - Remove a watch
  6. get_supported_platforms - List supported stores
  7. health_check - Check backend status

🚀 Ready to receive requests!
```

## 📚 Available Tools

### 1. `fetch_product`
Fetch product details and real-time price from supported platforms.

**Parameters:**
- `url` (required): Product URL from Amazon, Flipkart, Myntra, or Snapdeal
- `comparison` (optional): Include cross-platform comparison (default: true)

**Example Response:**
```
✅ Product Found: iPhone 15 Pro Max

💰 Price: ₹139,999
📊 Platform: AMAZON
⭐ Rating: 4.8 / 5
📦 Availability: In Stock

🔄 Price Comparison:
  • AMAZON: ₹139,999 = 0
  • FLIPKART: ₹135,000 ↓ 4,999
  • MYNTRA: Not Available
  • SNAPDEAL: ₹138,999 ↓ 1,000

📈 Price History: 12 data points
```

### 2. `get_price_history`
Retrieve historical price data for trend analysis.

**Parameters:**
- `url` (required): Product URL

**Returns:**
- Current price
- Lowest and highest recorded prices
- Trend direction (increasing/decreasing/stable)
- Recent price points with timestamps

### 3. `create_price_watch`
Set up automated price monitoring with email alerts.

**Parameters:**
- `url` (required): Product URL to watch
- `target_price` (required): Target price in ₹
- `email` (required): Email for notifications

**Features:**
- Daily automatic price checks
- Email notification when target reached
- Persistent watch across restarts

### 4. `list_price_watches`
View all active price watches.

**Returns:**
- Watch ID
- Product title
- Target price
- Email address
- Status (active/inactive)

### 5. `delete_price_watch`
Remove a price watch by ID.

**Parameters:**
- `watch_id` (required): ID from list_price_watches

### 6. `get_supported_platforms`
List all supported e-commerce platforms with details.

**Returns:**
- Platform name and domain
- Product categories covered
- Available features

### 7. `health_check`
Verify backend connectivity and status.

**Returns:**
- Backend status
- API configuration
- Available features

## 🔧 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AI Assistant (Claude, ChatGPT, etc.)     │
└────────────────┬────────────────────────────────────────────┘
                 │ MCP Protocol
                 │
┌────────────────▼────────────────────────────────────────────┐
│              Stitch MCP Server (server.py)                   │
│  • Exposes 7 tools for AI assistants                         │
│  • Validates requests                                        │
│  • Formats responses                                         │
│  • Handles errors gracefully                                 │
└────────────────┬────────────────────────────────────────────┘
                 │ HTTP/JSON
                 │
┌────────────────▼────────────────────────────────────────────┐
│         Price Tracker FastAPI Backend (main.py)              │
│  • Real-time scraping (Selenium, Session, Direct)            │
│  • Platform-specific parsers (Amazon, Flipkart, etc.)        │
│  • SQLite price history database                             │
│  • Email notification system                                 │
│  • Price watch automation                                    │
└────────────────┬────────────────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────────────────┐
│              E-Commerce Platforms                            │
│  • Amazon.in    • Flipkart    • Myntra    • Snapdeal        │
└─────────────────────────────────────────────────────────────┘
```

## 🔌 Integration Guide

### With Claude (Anthropic)
```python
from anthropic import Anthropic

client = Anthropic()

# Claude can now call Price Tracker tools through MCP
response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    tools=[...],  # Tools from your MCP server
    messages=[
        {"role": "user", "content": "Find the cheapest iPhone 15 price"}
    ]
)
```

### With OpenAI (ChatGPT)
```python
from openai import OpenAI

client = OpenAI()

# Similar integration pattern for OpenAI
completion = client.chat.completions.create(
    model="gpt-4",
    tools=[...],  # Tools from your MCP server
    messages=[...]
)
```

### Direct API Calls
```bash
# Check if MCP server is running
curl http://localhost:3001/health

# Fetch a product (through your MCP server)
curl -X POST http://localhost:3001/fetch_product \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.amazon.in/dp/..."}'
```

## 📊 Use Cases

### 1. **Smart Shopping Assistant**
"Find me the cheapest iPhone 15 across all platforms"
- MCP fetches product from multiple sites
- Compares prices
- Returns best deal with savings

### 2. **Price Drop Alerts**
"Alert me when the MacBook Pro drops below ₹1,50,000"
- Creates price watch
- Monitors daily
- Sends email notification

### 3. **Price Trend Analysis**
"Show me the price trend for this laptop over the last month"
- Retrieves historical data
- Analyzes trends
- Provides insights

### 4. **Bulk Product Research**
"Compare prices for these 10 products across all platforms"
- Fetches all products
- Compares prices
- Generates report

## 🛠️ Configuration Options

### Basic Setup
```bash
# Minimal setup - just the backend connection
PRICE_TRACKER_API=http://localhost:8000
MCP_PORT=3001
```

### Cloud Integration (Optional)

**Google Cloud:**
```bash
GCP_PROJECT_ID=my-project
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
BIGQUERY_DATASET=price_tracker
```

**AWS:**
```bash
AWS_REGION=us-east-1
S3_BUCKET=price-tracker-data
DYNAMODB_TABLE=price_watches
```

## 🔒 Security Considerations

### Current Implementation
- ✅ Direct connection to local backend
- ✅ No authentication required (local network)
- ✅ Input validation on all parameters
- ✅ Error messages don't leak sensitive data

### For Production Deployment
- [ ] Add API key authentication
- [ ] Enable HTTPS/TLS encryption
- [ ] Implement request rate limiting
- [ ] Add request logging and monitoring
- [ ] Use environment variables for secrets
- [ ] Validate all inputs with Pydantic schemas

## 📈 Monitoring & Logging

Check server logs for activity:

```bash
# Real-time logs
tail -f mcp-server.log

# With verbose logging enabled
LOG_LEVEL=DEBUG python server.py
```

Key metrics to monitor:
- Tool invocation count
- Response times
- Error rates
- Backend connectivity status

## 🚨 Troubleshooting

### MCP Server won't start
```bash
# Check if port 3001 is in use
lsof -i :3001

# Kill the process if needed
kill -9 <PID>

# Try a different port
MCP_PORT=3002 python server.py
```

### Can't connect to backend
```bash
# Verify backend is running
curl http://localhost:8000/api/health

# Check if URL is correct in .env
PRICE_TRACKER_API=http://localhost:8000

# Test direct connection
python -c "import httpx; print(httpx.get('http://localhost:8000/api/health').json())"
```

### Tool returns errors
```bash
# Enable verbose logging
VERBOSE_LOGGING=true python server.py

# Check if all required parameters are provided
# Refer to tool documentation above
```

## 📦 Deployment Options

### Local Development
```bash
python server.py
# Runs on http://localhost:3001
```

### Docker
```bash
docker build -t price-tracker-mcp .
docker run -p 3001:3001 \
  -e PRICE_TRACKER_API=http://host.docker.internal:8000 \
  price-tracker-mcp
```

### Cloud (AWS Lambda, Google Cloud Functions)
```bash
# Export as serverless function
# Trigger from API Gateway
# Invoke from AI assistant endpoints
```

## 🔄 Integration with Price Tracker Features

### Real-time Scraping
```
MCP fetch_product
  → Calls Price Tracker API
    → Selenium/Session/Direct scraping
      → Platform-specific parsing
        → Returns live prices
```

### Price Comparison
```
MCP fetch_product (with comparison=true)
  → Calls Price Tracker API
    → Builds search URLs for all platforms
      → Scrapes search results
        → Compares top results
          → Returns comparison table
```

### Price Watches
```
MCP create_price_watch
  → Stores watch in SQLite
    → Background task checks daily
      → Detects price drops
        → Sends email notification
```

## 📚 Examples

### Example 1: Find Cheapest Deal
```python
# Using MCP directly
result = await fetch_product(
    url="https://www.amazon.in/dp/B0CVWB3KWY",
    comparison=True
)
# Returns best price across all platforms
```

### Example 2: Set Price Alert
```python
result = await create_price_watch(
    url="https://www.flipkart.com/p/...",
    target_price=50000,
    email="user@example.com"
)
# Watches price daily, emails when target reached
```

### Example 3: Analyze Price Trend
```python
history = await get_price_history(
    url="https://www.myntra.com/p/..."
)
# Shows price movement over time
```

## 🤝 Contributing

To add new tools:

1. Define the tool function with async support
2. Register it with `app.add_tool()`
3. Include proper docstrings and parameter validation
4. Add error handling for all API calls
5. Update this README with examples

## 📄 License

Same as Price Tracker project

## 🆘 Support

- **Backend Issues**: See `../backend/README.md`
- **Frontend Issues**: See `../frontend/README.md`
- **API Documentation**: Check Price Tracker FastAPI endpoints
- **MCP Specification**: https://modelcontextprotocol.io/

---

**Last Updated**: March 2026  
**Status**: Production Ready ✅  
**Tools Available**: 7  
**Supported Platforms**: 4 (Amazon, Flipkart, Myntra, Snapdeal)
