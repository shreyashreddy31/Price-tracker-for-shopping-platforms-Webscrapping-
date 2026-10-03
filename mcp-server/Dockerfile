FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy server code
COPY server.py .
COPY .env .

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:3001/health || exit 1

# Environment variables (can be overridden at runtime)
ENV PRICE_TRACKER_API=http://localhost:8000
ENV MCP_PORT=3001
ENV LOG_LEVEL=INFO

# Expose port
EXPOSE 3001

# Run the server
CMD ["python", "server.py"]
