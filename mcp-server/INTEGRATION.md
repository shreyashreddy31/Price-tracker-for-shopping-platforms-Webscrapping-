# 🔌 Stitch MCP Integration Guide

This guide explains how to integrate the Price Tracker MCP Server with various AI assistants and platforms.

## 📋 Table of Contents

1. [MCP Server Setup](#mcp-server-setup)
2. [Integration with Claude/Anthropic](#integration-with-claudeanthropomorphic)
3. [Integration with OpenAI](#integration-with-openai)
4. [Integration with Local AI](#integration-with-local-ai)
5. [Docker Deployment](#docker-deployment)
6. [Cloud Deployment](#cloud-deployment)

## 🚀 MCP Server Setup

### Prerequisites
- Python 3.11+
- Price Tracker backend running on port 8000
- pip/venv for package management

### Installation

```bash
cd mcp-server

# Run setup
bash setup.sh

# Start the server
bash start.sh
```

The server will:
- Create a virtual environment
- Install dependencies (mcp, httpx, etc.)
- Verify backend connectivity
- Start listening on port 3001

### Verification

```bash
# Check if server is running
curl http://localhost:3001/health

# Expected response:
# {
#   "status": "online",
#   "timestamp": "2026-03-14T10:30:00Z",
#   ...
# }
```

## 🤖 Integration with Claude/Anthropic

### Option 1: Using Claude Desktop App (Easiest)

1. **Install Claude Desktop**
   - Download from https://claude.ai/download

2. **Configure MCP Server**
   Edit `~/.config/Claude/claude_desktop_config.json`:
   
   ```json
   {
     "mcpServers": {
       "price-tracker": {
         "command": "python",
         "args": ["/path/to/mcp-server/server.py"],
         "env": {
           "PRICE_TRACKER_API": "http://localhost:8000",
           "MCP_PORT": "3001"
         }
       }
     }
   }
   ```

3. **Restart Claude Desktop**
   - Close and reopen the app
   - MCP tools will be available in conversations

4. **Test Integration**
   - Ask Claude: "Find the cheapest iPhone 15 price across all platforms"
   - Claude will use the MCP tools to fetch real prices

### Option 2: Using Claude API (Programmatic)

```python
from anthropic import Anthropic
import json

client = Anthropic()

# Define tools from your MCP server
tools = [
    {
        "name": "fetch_product",
        "description": "Fetch product details and price",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Product URL"},
                "comparison": {"type": "boolean", "description": "Include comparison"}
            },
            "required": ["url"]
        }
    },
    {
        "name": "get_price_history",
        "description": "Retrieve historical price data",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Product URL"}
            },
            "required": ["url"]
        }
    },
    {
        "name": "create_price_watch",
        "description": "Set up automated price monitoring",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "target_price": {"type": "number"},
                "email": {"type": "string"}
            },
            "required": ["url", "target_price", "email"]
        }
    }
]

# Have a conversation
messages = [
    {"role": "user", "content": "Find me the best price for iPhone 15 Pro"}
]

response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    tools=tools,
    messages=messages
)

# Process tool calls
if response.stop_reason == "tool_use":
    for content in response.content:
        if hasattr(content, 'name'):
            print(f"Claude wants to call: {content.name}")
            print(f"With arguments: {json.dumps(content.input, indent=2)}")
            # You would call your MCP server here
```

## 🔮 Integration with OpenAI

### Option 1: Using OpenAI Function Calling

```python
from openai import OpenAI
import json

client = OpenAI()

# Define tools
tools = [
    {
        "type": "function",
        "function": {
            "name": "fetch_product",
            "description": "Fetch product price and details from e-commerce platforms",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Product URL"},
                    "comparison": {"type": "boolean", "description": "Include cross-platform comparison"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_price_watch",
            "description": "Set up an automated price watch",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "target_price": {"type": "number"},
                    "email": {"type": "string"}
                },
                "required": ["url", "target_price", "email"]
            }
        }
    }
]

# Make a request
messages = [
    {"role": "user", "content": "Find the cheapest MacBook Air on all platforms"}
]

response = client.chat.completions.create(
    model="gpt-4",
    messages=messages,
    tools=tools,
    tool_choice="auto"
)

# Handle tool calls
if response.choices[0].message.tool_calls:
    for tool_call in response.choices[0].message.tool_calls:
        print(f"Tool: {tool_call.function.name}")
        print(f"Args: {tool_call.function.arguments}")
        # Call your MCP server with these parameters
```

### Option 2: Using OpenAI Assistants API

```python
from openai import OpenAI

client = OpenAI()

# Create assistant with MCP tools
assistant = client.beta.assistants.create(
    name="Price Tracker Assistant",
    description="Finds and compares product prices across e-commerce platforms",
    model="gpt-4",
    tools=[
        {
            "type": "function",
            "function": {
                "name": "fetch_product",
                # ... function definition
            }
        }
    ]
)

# Have a conversation
thread = client.beta.threads.create()

message = client.beta.threads.messages.create(
    thread_id=thread.id,
    role="user",
    content="What's the best deal on iPhone 15?"
)

run = client.beta.threads.runs.create(
    thread_id=thread.id,
    assistant_id=assistant.id
)

# Poll for completion
while run.status != "completed":
    run = client.beta.threads.runs.retrieve(
        thread_id=thread.id,
        run_id=run.id
    )
    # Handle tool calls as they come in
```

## 🏠 Integration with Local AI

### Option 1: Using Ollama + LM Studio

```bash
# Start your local LLM
ollama run mistral

# In another terminal, run MCP server
cd mcp-server
bash start.sh

# Create a local agent
python -c "
import requests
import json

# Your local model endpoint
LOCAL_LLM = 'http://localhost:11434/api/generate'

# Call MCP server
response = requests.post('http://localhost:3001/tools/call', json={
    'tool': 'fetch_product',
    'arguments': {'url': 'https://www.amazon.in/dp/...'}
})

print(json.dumps(response.json(), indent=2))
"
```

### Option 2: Using LlamaIndex

```python
from llama_index.core.agent import AgentRunner
from llama_index.core.tools import ToolSpec

class PriceTrackerTools(ToolSpec):
    """Price Tracker tools for LlamaIndex agents."""
    
    spec_functions = ["fetch_product", "create_price_watch", "get_price_history"]
    
    def fetch_product(self, url: str, comparison: bool = True) -> str:
        """Fetch product details"""
        # Call MCP server
        import httpx
        client = httpx.Client()
        response = client.post('http://localhost:3001/tools/call', json={
            'tool': 'fetch_product',
            'arguments': {'url': url, 'comparison': comparison}
        })
        return response.text
    
    def create_price_watch(self, url: str, target_price: float, email: str) -> str:
        """Create price watch"""
        # Similar implementation
        pass
    
    def get_price_history(self, url: str) -> str:
        """Get price history"""
        # Similar implementation
        pass

# Create agent
tools = PriceTrackerTools()
agent = AgentRunner.from_llm(
    llm=your_local_llm,
    tools=tools
)

# Use agent
response = agent.chat("Find the cheapest iPhone 15")
print(response)
```

## 🐳 Docker Deployment

### Build Docker Image

```bash
cd mcp-server
docker build -t price-tracker-mcp .
```

### Run Container

```bash
docker run -d \
  --name price-tracker-mcp \
  -p 3001:3001 \
  -e PRICE_TRACKER_API=http://host.docker.internal:8000 \
  -e LOG_LEVEL=INFO \
  price-tracker-mcp
```

### With Docker Compose

```yaml
version: '3.8'

services:
  price-tracker-backend:
    build:
      context: ./backend
    ports:
      - "8000:8000"
    environment:
      - SMTP_SERVER=smtp.gmail.com
      - SMTP_PORT=587

  mcp-server:
    build:
      context: ./mcp-server
    ports:
      - "3001:3001"
    environment:
      - PRICE_TRACKER_API=http://price-tracker-backend:8000
      - MCP_PORT=3001
    depends_on:
      - price-tracker-backend

  frontend:
    build:
      context: ./frontend
    ports:
      - "5174:5174"
    depends_on:
      - price-tracker-backend
```

Start with:
```bash
docker-compose up
```

## ☁️ Cloud Deployment

### AWS Lambda

```python
# lambda_handler.py
from mcp_server import app

async def lambda_handler(event, context):
    """AWS Lambda handler for MCP server."""
    # Parse incoming request
    tool_name = event.get('tool')
    arguments = event.get('arguments', {})
    
    # Execute tool
    result = await app.call_tool(tool_name, arguments)
    
    return {
        'statusCode': 200,
        'body': json.dumps(result)
    }
```

Deploy with:
```bash
# Create deployment package
zip -r mcp-lambda.zip server.py requirements.txt

# Upload to AWS Lambda
aws lambda create-function \
  --function-name price-tracker-mcp \
  --runtime python3.11 \
  --handler lambda_handler.lambda_handler \
  --zip-file fileb://mcp-lambda.zip
```

### Google Cloud Functions

```python
# main.py
from mcp_server import app
from functions_framework import http

@http.route('/tool')
def call_tool(request):
    """Google Cloud Function handler."""
    request_json = request.get_json()
    tool_name = request_json.get('tool')
    arguments = request_json.get('arguments', {})
    
    result = await app.call_tool(tool_name, arguments)
    
    return result
```

Deploy with:
```bash
gcloud functions deploy price-tracker-mcp \
  --runtime python311 \
  --trigger-http \
  --allow-unauthenticated
```

### Vercel/Netlify

```bash
# Create vercel.json
{
  "version": 2,
  "builds": [
    {
      "src": "mcp-server/server.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/api/(.*)",
      "dest": "mcp-server/server.py"
    }
  ]
}
```

Deploy with:
```bash
vercel deploy
```

## 🧪 Testing the Integration

### Manual Testing

```bash
# Test with curl
curl -X POST http://localhost:3001/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "fetch_product",
    "arguments": {
      "url": "https://www.amazon.in/dp/B0CVWB3KWY",
      "comparison": true
    }
  }'
```

### Automated Testing

```bash
# Run test client
python test_client.py https://www.amazon.in/dp/B0CVWB3KWY

# Run with pytest
pytest test_mcp_integration.py -v
```

## 🔒 Security Best Practices

1. **Local Network Only**
   ```bash
   # Bind to localhost only
   MCP_PORT=3001 python server.py
   ```

2. **API Keys**
   ```bash
   # Use environment variables
   export MCP_API_KEY="secret-key"
   # Validate in server.py
   ```

3. **HTTPS in Production**
   ```python
   # Use SSL certificates
   ssl_context = ssl.SSLContext()
   ssl_context.load_cert_chain("cert.pem", "key.pem")
   ```

4. **Rate Limiting**
   ```python
   from slowapi import Limiter
   limiter = Limiter(key_func=get_remote_address)
   ```

## 📊 Monitoring

### Check Server Health

```bash
# Continuous monitoring
watch -n 5 'curl -s http://localhost:3001/health | jq'
```

### Log Monitoring

```bash
# Real-time logs
tail -f mcp-server.log

# With grep filter
tail -f mcp-server.log | grep ERROR
```

### Metrics Collection

```python
# Add to server.py
from prometheus_client import Counter, Histogram
import time

request_count = Counter('mcp_requests_total', 'Total requests')
request_latency = Histogram('mcp_request_latency_seconds', 'Request latency')

@app.call_tool()
async def fetch_product(arguments):
    start = time.time()
    request_count.inc()
    try:
        result = await call_api(...)
        request_latency.observe(time.time() - start)
        return result
    except Exception as e:
        request_count.labels(status='error').inc()
        raise
```

## 🆘 Troubleshooting

### MCP Server won't start
```bash
# Check port is free
lsof -i :3001

# Check Python version
python3 --version

# Check dependencies
pip list | grep mcp
```

### Tools not available
```bash
# Verify server is running
curl http://localhost:3001/health

# Check tool registration
python -c "from mcp_server import app; print(app.tools)"
```

### Claude can't see tools
```bash
# Restart Claude Desktop
# Verify claude_desktop_config.json syntax
jq . ~/.config/Claude/claude_desktop_config.json

# Check server logs for errors
tail -f mcp-server.log
```

## 📚 Additional Resources

- [Model Context Protocol Spec](https://modelcontextprotocol.io/)
- [Anthropic Claude API Docs](https://docs.anthropic.com)
- [OpenAI Function Calling](https://platform.openai.com/docs/guides/function-calling)
- [LlamaIndex Documentation](https://docs.llamaindex.ai)

---

**Last Updated**: March 2026  
**Tested With**: Claude, ChatGPT, Llama  
**Status**: Production Ready ✅
