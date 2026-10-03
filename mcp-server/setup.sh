#!/bin/bash
# Setup script for Stitch MCP Server

set -e

echo "╔═══════════════════════════════════════════════════════╗"
echo "║   🛒 Price Tracker - Stitch MCP Server Setup         ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""

# Check Python version
echo "📌 Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "   ✅ Python $PYTHON_VERSION"
echo ""

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    echo "   ✅ Virtual environment created"
else
    echo "   ✅ Virtual environment already exists"
fi
echo ""

# Activate virtual environment
echo "🚀 Activating virtual environment..."
source venv/bin/activate
echo "   ✅ Virtual environment activated"
echo ""

# Install dependencies
echo "📚 Installing dependencies..."
pip install -q -r requirements.txt
echo "   ✅ Dependencies installed"
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚙️  Creating .env file with defaults..."
    cat > .env << 'EOF'
PRICE_TRACKER_API=http://localhost:8000
MCP_PORT=3001
LOG_LEVEL=INFO
VERBOSE_LOGGING=false
EOF
    echo "   ✅ .env file created"
else
    echo "   ✅ .env file already exists"
fi
echo ""

# Verify backend connectivity
echo "🔌 Checking backend connectivity..."
BACKEND_URL=$(grep PRICE_TRACKER_API .env | cut -d'=' -f2)
if curl -s -f "$BACKEND_URL/api/health" > /dev/null 2>&1; then
    echo "   ✅ Backend is online and reachable"
else
    echo "   ⚠️  Backend is not running. Start it with:"
    echo "      cd ../backend && source venv/bin/activate && uvicorn main:app --reload --port 8000"
fi
echo ""

echo "╔═══════════════════════════════════════════════════════╗"
echo "║            ✅ Setup Complete!                        ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""
echo "🚀 To start the MCP server, run:"
echo "   source venv/bin/activate && python server.py"
echo ""
echo "📚 For more information, see README.md"
echo ""
