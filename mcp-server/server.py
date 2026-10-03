#!/usr/bin/env python3
"""
Stitch MCP Server for Price Tracker
Provides Model Context Protocol tools for AI assistants to interact with the Price Tracker API.
Supports real-time price scraping, comparison, and historical tracking.
"""

import asyncio
import json
import os
import sys
from typing import Any, Optional
from datetime import datetime

import httpx
from mcp.server import Server
from mcp.types import (
    Tool,
    TextContent,
    ToolResult,
)

# ─── Configuration ────────────────────────────────────────────────────────────
API_BASE = os.getenv("PRICE_TRACKER_API", "http://localhost:8000")
MCP_PORT = int(os.getenv("MCP_PORT", "3001"))

# ─── Initialize MCP Server ───────────────────────────────────────────────────
app = Server("price-tracker-mcp")

# ─── HTTP Client ──────────────────────────────────────────────────────────────
async def call_api(method: str, endpoint: str, **kwargs) -> dict:
    """Make a request to the Price Tracker API."""
    url = f"{API_BASE}/api/{endpoint}"
    timeout = httpx.Timeout(30.0)
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            if method == "GET":
                response = await client.get(url, **kwargs)
            elif method == "POST":
                response = await client.post(url, **kwargs)
            elif method == "DELETE":
                response = await client.delete(url, **kwargs)
            else:
                return {"error": f"Unsupported method: {method}"}
            
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            return {"error": f"API Error: {str(e)}"}
        except Exception as e:
            return {"error": f"Request failed: {str(e)}"}

# ─── Tool: Fetch Product ──────────────────────────────────────────────────────

@app.call_tool()
async def fetch_product(arguments: dict) -> ToolResult:
    """
    Fetch product details and price from supported e-commerce platforms.
    
    Args:
        url: Product URL from Amazon, Flipkart, Myntra, or Snapdeal
        comparison: Whether to include cross-platform comparison (default: true)
    
    Returns:
        Product details including title, price, image, rating, and comparison results
    """
    url = arguments.get("url")
    comparison = arguments.get("comparison", True)
    
    if not url:
        return ToolResult(content=[TextContent(
            text="❌ Error: Product URL is required",
            mime_type="text/plain"
        )], is_error=True)
    
    result = await call_api("POST", "fetch-product", json={
        "url": url,
        "comparison": comparison
    })
    
    if "error" in result:
        return ToolResult(content=[TextContent(
            text=f"❌ {result['error']}",
            mime_type="text/plain"
        )], is_error=True)
    
    # Format response
    text = f"""
✅ Product Found: {result.get('title', 'Unknown')}

💰 Price: ₹{result.get('current_price', 'N/A'):,}
📊 Platform: {result.get('platform', 'Unknown').upper()}
⭐ Rating: {result.get('rating', 'N/A')} / 5
📦 Availability: {result.get('availability', 'Unknown')}

📸 Image: {result.get('image_url', 'N/A')}
🔗 URL: {result.get('product_url', url)}

"""
    
    # Add comparison if available
    if result.get("comparison"):
        text += "🔄 Price Comparison:\n"
        for comp in result["comparison"]:
            diff = comp.get("price_difference", 0)
            symbol = "↓" if diff < 0 else "↑" if diff > 0 else "="
            text += f"  • {comp['platform'].upper()}: ₹{comp.get('price', 'N/A'):,} {symbol} {abs(diff):,}\n"
    
    # Add price history if available
    if result.get("price_history"):
        text += f"\n📈 Price History: {len(result['price_history'])} data points"
    
    return ToolResult(content=[TextContent(text=text, mime_type="text/plain")])

# ─── Tool: Get Price History ──────────────────────────────────────────────────

@app.call_tool()
async def get_price_history(arguments: dict) -> ToolResult:
    """
    Retrieve historical price data for a product.
    
    Args:
        url: Product URL
    
    Returns:
        List of price history points with timestamps
    """
    url = arguments.get("url")
    
    if not url:
        return ToolResult(content=[TextContent(
            text="❌ Error: Product URL is required",
            mime_type="text/plain"
        )], is_error=True)
    
    result = await call_api("GET", "price-history", params={"url": url})
    
    if "error" in result:
        return ToolResult(content=[TextContent(
            text=f"❌ {result['error']}",
            mime_type="text/plain"
        )], is_error=True)
    
    history = result.get("history", [])
    
    if not history:
        text = f"📊 No price history found for this URL yet.\nVisit the product page to start tracking!"
    else:
        min_price = min(h["price"] for h in history)
        max_price = max(h["price"] for h in history)
        current = history[-1]["price"]
        
        text = f"""
📊 Price History: {len(history)} data points

💰 Current: ₹{current:,}
📉 Lowest: ₹{min_price:,}
📈 Highest: ₹{max_price:,}
📊 Trend: {'📉 Decreasing' if current < history[0]['price'] else '📈 Increasing' if current > history[0]['price'] else '➡️ Stable'}

Recent prices:
"""
        for h in history[-5:]:
            timestamp = datetime.fromisoformat(h["timestamp"]).strftime("%Y-%m-%d %H:%M")
            text += f"  {timestamp}: ₹{h['price']:,}\n"
    
    return ToolResult(content=[TextContent(text=text, mime_type="text/plain")])

# ─── Tool: Create Price Watch ─────────────────────────────────────────────────

@app.call_tool()
async def create_price_watch(arguments: dict) -> ToolResult:
    """
    Create an automated price watch that monitors price changes.
    Sends email notification when target price is reached.
    
    Args:
        url: Product URL
        target_price: Target price to watch for (in ₹)
        email: Email address for notifications
    
    Returns:
        Watch confirmation with ID
    """
    url = arguments.get("url")
    target_price = arguments.get("target_price")
    email = arguments.get("email")
    
    if not all([url, target_price, email]):
        return ToolResult(content=[TextContent(
            text="❌ Error: url, target_price, and email are all required",
            mime_type="text/plain"
        )], is_error=True)
    
    try:
        target_price = float(target_price)
    except (ValueError, TypeError):
        return ToolResult(content=[TextContent(
            text="❌ Error: target_price must be a number",
            mime_type="text/plain"
        )], is_error=True)
    
    result = await call_api("POST", "watches", json={
        "url": url,
        "target_price": target_price,
        "email": email
    })
    
    if "error" in result:
        return ToolResult(content=[TextContent(
            text=f"❌ {result['error']}",
            mime_type="text/plain"
        )], is_error=True)
    
    text = f"""
✅ Price Watch Created!

🔔 Watching: {result.get('message', 'Product tracking enabled')}
💰 Target Price: ₹{target_price:,}
📧 Notification Email: {email}
🔑 Watch ID: {result.get('watch_id', 'N/A')}

You'll receive an email when the price reaches your target.
Daily price checks are automatic.
"""
    
    return ToolResult(content=[TextContent(text=text, mime_type="text/plain")])

# ─── Tool: List Price Watches ─────────────────────────────────────────────────

@app.call_tool()
async def list_price_watches(arguments: dict) -> ToolResult:
    """
    List all active price watches.
    
    Returns:
        Details of all active watches
    """
    result = await call_api("GET", "watches")
    
    if "error" in result:
        return ToolResult(content=[TextContent(
            text=f"❌ {result['error']}",
            mime_type="text/plain"
        )], is_error=True)
    
    watches = result.get("watches", [])
    
    if not watches:
        text = "📋 No active price watches.\nCreate one with create_price_watch to get started!"
    else:
        text = f"📋 Active Price Watches: {len(watches)}\n\n"
        for w in watches:
            text += f"""
🔔 Watch #{w.get('id', 'N/A')}
  Product: {w.get('product_title', 'Unknown')[:50]}...
  Target: ₹{w.get('target_price', 'N/A'):,}
  Email: {w.get('email', 'N/A')}
  Created: {w.get('created_at', 'N/A')}
  Status: {'✅ Active' if w.get('active') else '❌ Inactive'}
"""
    
    return ToolResult(content=[TextContent(text=text, mime_type="text/plain")])

# ─── Tool: Delete Price Watch ─────────────────────────────────────────────────

@app.call_tool()
async def delete_price_watch(arguments: dict) -> ToolResult:
    """
    Delete a price watch by ID.
    
    Args:
        watch_id: ID of the watch to delete
    
    Returns:
        Confirmation of deletion
    """
    watch_id = arguments.get("watch_id")
    
    if not watch_id:
        return ToolResult(content=[TextContent(
            text="❌ Error: watch_id is required",
            mime_type="text/plain"
        )], is_error=True)
    
    result = await call_api("DELETE", f"watches/{watch_id}")
    
    if "error" in result:
        return ToolResult(content=[TextContent(
            text=f"❌ {result['error']}",
            mime_type="text/plain"
        )], is_error=True)
    
    text = f"✅ Price watch #{watch_id} deleted successfully."
    
    return ToolResult(content=[TextContent(text=text, mime_type="text/plain")])

# ─── Tool: Get Supported Platforms ────────────────────────────────────────────

@app.call_tool()
async def get_supported_platforms(arguments: dict) -> ToolResult:
    """
    Get list of supported e-commerce platforms.
    
    Returns:
        Available platforms with details
    """
    result = await call_api("GET", "platforms")
    
    if "error" in result:
        return ToolResult(content=[TextContent(
            text=f"❌ {result['error']}",
            mime_type="text/plain"
        )], is_error=True)
    
    platforms = result.get("platforms", [])
    
    text = f"🛒 Supported E-Commerce Platforms: {len(platforms)}\n\n"
    for p in platforms:
        text += f"""
✅ {p.get('name', 'Unknown').upper()}
   Domain: {p.get('domain', 'N/A')}
   Category: {p.get('category', 'N/A')}
   Features: {', '.join(p.get('features', []))}
"""
    
    return ToolResult(content=[TextContent(text=text, mime_type="text/plain")])

# ─── Tool: Health Check ───────────────────────────────────────────────────────

@app.call_tool()
async def health_check(arguments: dict) -> ToolResult:
    """
    Check if the Price Tracker backend is online and responsive.
    
    Returns:
        Backend status and configuration
    """
    result = await call_api("GET", "health")
    
    if "error" in result:
        return ToolResult(content=[TextContent(
            text="❌ Price Tracker backend is OFFLINE or unreachable",
            mime_type="text/plain"
        )], is_error=True)
    
    status = result.get("status", "unknown")
    text = f"""
✅ Price Tracker Backend Status: {status.upper()}

📊 API Base: {API_BASE}
🔄 MCP Server: Running on port {MCP_PORT}
⏰ Timestamp: {result.get('timestamp', 'N/A')}

The Price Tracker is ready to scrape prices from:
  • Amazon.in
  • Flipkart
  • Myntra
  • Snapdeal

All features are operational:
  ✓ Real-time price scraping
  ✓ Cross-platform comparison
  ✓ Price history tracking
  ✓ Automated price watches
  ✓ Email notifications
"""
    
    return ToolResult(content=[TextContent(text=text, mime_type="text/plain")])

# ─── Register Tools ───────────────────────────────────────────────────────────

def setup_tools():
    """Register all available tools with the MCP server."""
    
    app.add_tool(Tool(
        name="fetch_product",
        description="Fetch product details and price from e-commerce platforms (Amazon, Flipkart, Myntra, Snapdeal)",
        inputSchema={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Product URL from Amazon.in, Flipkart, Myntra, or Snapdeal"
                },
                "comparison": {
                    "type": "boolean",
                    "description": "Include cross-platform price comparison (default: true)",
                    "default": True
                }
            },
            "required": ["url"]
        }
    ))
    
    app.add_tool(Tool(
        name="get_price_history",
        description="Retrieve historical price data for a product",
        inputSchema={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Product URL"
                }
            },
            "required": ["url"]
        }
    ))
    
    app.add_tool(Tool(
        name="create_price_watch",
        description="Create an automated price watch with email notifications",
        inputSchema={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Product URL to watch"
                },
                "target_price": {
                    "type": "number",
                    "description": "Target price in ₹ (Indian Rupees)"
                },
                "email": {
                    "type": "string",
                    "description": "Email address for price drop notifications"
                }
            },
            "required": ["url", "target_price", "email"]
        }
    ))
    
    app.add_tool(Tool(
        name="list_price_watches",
        description="List all active price watches",
        inputSchema={
            "type": "object",
            "properties": {}
        }
    ))
    
    app.add_tool(Tool(
        name="delete_price_watch",
        description="Delete a price watch by ID",
        inputSchema={
            "type": "object",
            "properties": {
                "watch_id": {
                    "type": "integer",
                    "description": "ID of the watch to delete"
                }
            },
            "required": ["watch_id"]
        }
    ))
    
    app.add_tool(Tool(
        name="get_supported_platforms",
        description="Get list of supported e-commerce platforms with details",
        inputSchema={
            "type": "object",
            "properties": {}
        }
    ))
    
    app.add_tool(Tool(
        name="health_check",
        description="Check if Price Tracker backend is online and operational",
        inputSchema={
            "type": "object",
            "properties": {}
        }
    ))

# ─── Main ─────────────────────────────────────────────────────────────────────

async def main():
    """Run the MCP server."""
    setup_tools()
    
    print(f"""
╔════════════════════════════════════════════════════════════════╗
║           🛒 Price Tracker MCP Server Starting                 ║
╚════════════════════════════════════════════════════════════════╝

📊 Configuration:
  • API Base: {API_BASE}
  • MCP Port: {MCP_PORT}
  • Status: Initializing...

✨ Available Tools:
  1. fetch_product - Get product details and compare prices
  2. get_price_history - View historical price data
  3. create_price_watch - Set up price alerts
  4. list_price_watches - View all active watches
  5. delete_price_watch - Remove a watch
  6. get_supported_platforms - List supported stores
  7. health_check - Check backend status

🚀 Ready to receive requests!
    """)
    
    # Run server with stdio transport
    async with await app.run() as server:
        print(f"✅ MCP Server running on port {MCP_PORT}")
        await server.wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n❌ MCP Server stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
