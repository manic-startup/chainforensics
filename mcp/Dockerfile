# ChainForensics MCP Server Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir httpx mcp pydantic

# Copy MCP server
COPY server.py .

# Create non-root user
RUN useradd -m -u 1000 mcp
USER mcp

# MCP uses stdio, not network ports
CMD ["python", "server.py"]
