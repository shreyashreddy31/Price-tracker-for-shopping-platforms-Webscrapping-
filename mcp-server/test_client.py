#!/usr/bin/env python3
"""
Example client for testing the Stitch MCP Server.
Demonstrates how to call MCP tools programmatically.
"""

import asyncio
import json
import sys
from typing import Optional

import httpx


class PriceTrackerMCPClient:
    """Client for interacting with the Price Tracker MCP Server."""
    
    def __init__(self, mcp_url: str = "http://localhost:3001"):
        self.mcp_url = mcp_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def health_check(self) -> dict:
        """Check if MCP server is online."""
        try:
            response = await self.client.get(f"{self.mcp_url}/health")
            return response.json()
        except Exception as e:
            return {"error": f"Connection failed: {e}"}
    
    async def fetch_product(self, url: str, comparison: bool = True) -> dict:
        """Fetch product details from e-commerce platform."""
        payload = {
            "tool": "fetch_product",
            "arguments": {
                "url": url,
                "comparison": comparison
            }
        }
        try:
            response = await self.client.post(
                f"{self.mcp_url}/tools/call",
                json=payload
            )
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    async def get_price_history(self, url: str) -> dict:
        """Get price history for a product."""
        payload = {
            "tool": "get_price_history",
            "arguments": {"url": url}
        }
        try:
            response = await self.client.post(
                f"{self.mcp_url}/tools/call",
                json=payload
            )
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    async def create_watch(self, url: str, target_price: float, email: str) -> dict:
        """Create a price watch."""
        payload = {
            "tool": "create_price_watch",
            "arguments": {
                "url": url,
                "target_price": target_price,
                "email": email
            }
        }
        try:
            response = await self.client.post(
                f"{self.mcp_url}/tools/call",
                json=payload
            )
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    async def list_watches(self) -> dict:
        """List all active price watches."""
        payload = {
            "tool": "list_price_watches",
            "arguments": {}
        }
        try:
            response = await self.client.post(
                f"{self.mcp_url}/tools/call",
                json=payload
            )
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    async def get_platforms(self) -> dict:
        """Get supported platforms."""
        payload = {
            "tool": "get_supported_platforms",
            "arguments": {}
        }
        try:
            response = await self.client.post(
                f"{self.mcp_url}/tools/call",
                json=payload
            )
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    async def close(self):
        """Close the client connection."""
        await self.client.aclose()


async def main():
    """Run example tests."""
    print("╔═══════════════════════════════════════════════════════╗")
    print("║   🛒 Price Tracker MCP Client Examples               ║")
    print("╚═══════════════════════════════════════════════════════╝")
    print()
    
    client = PriceTrackerMCPClient()
    
    # Test 1: Health check
    print("📌 Test 1: Health Check")
    print("─" * 55)
    result = await client.health_check()
    print(json.dumps(result, indent=2))
    print()
    
    # Test 2: Get supported platforms
    print("📌 Test 2: Supported Platforms")
    print("─" * 55)
    result = await client.get_platforms()
    print(json.dumps(result, indent=2))
    print()
    
    # Test 3: Fetch product (example URL - replace with real)
    print("📌 Test 3: Fetch Product")
    print("─" * 55)
    print("Example: To test this, use a real product URL:")
    print("  python test_client.py https://www.amazon.in/dp/B0CVWB3KWY")
    print()
    
    # Accept URL from command line
    if len(sys.argv) > 1:
        url = sys.argv[1]
        print(f"Fetching: {url}")
        result = await client.fetch_product(url, comparison=True)
        print(json.dumps(result, indent=2))
        print()
        
        # Test 4: Get price history
        print("📌 Test 4: Price History")
        print("─" * 55)
        result = await client.get_price_history(url)
        print(json.dumps(result, indent=2))
        print()
    
    # Test 5: List watches
    print("📌 Test 5: List Price Watches")
    print("─" * 55)
    result = await client.list_watches()
    print(json.dumps(result, indent=2))
    print()
    
    await client.close()
    
    print("✅ Tests completed!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n❌ Tests interrupted")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
