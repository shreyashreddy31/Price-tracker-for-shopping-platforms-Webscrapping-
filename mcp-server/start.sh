#!/bin/bash
# Quick start script for Stitch MCP Server

set -e

echo "╔═══════════════════════════════════════════════════════╗"
echo "║   🛒 Starting Price Tracker MCP Server               ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""

# Check if backend is running
BACKEND_URL=${PRICE_TRACKER_API:-http://localhost:8000}
echo "🔌 Checking backend at $BACKEND_URL..."

if ! curl -s -f "$BACKEND_URL/api/health" > /dev/null 2>&1; then
    echo "❌ Error: Backend is not running!"
    echo ""
    echo "📍 Start the backend with:"
    echo "   cd ../backend"
    echo "   source venv/bin/activate"
    echo "   uvicorn main:app --reload --port 8000"
    echo ""
    exit 1
fi

echo "✅ Backend is online!"
echo ""

# Activate venv if not already active
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "🐍 Activating virtual environment..."
    source venv/bin/activate
fi

echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║   🚀 Starting MCP Server...                          ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""

# Run the server
python server.py
