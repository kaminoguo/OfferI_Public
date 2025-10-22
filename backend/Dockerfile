# OfferI Backend Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for WeasyPrint (PDF generation) and Node.js for Claude CLI
RUN apt-get update && apt-get install -y \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    libcairo2 \
    libcairo2-dev \
    libglib2.0-0 \
    libglib2.0-dev \
    libharfbuzz-dev \
    libpangocairo-1.0-0 \
    shared-mime-info \
    curl \
    ca-certificates \
    gnupg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI via npm
RUN npm install -g @anthropic-ai/claude-code

# Copy requirements first (for Docker layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code INCLUDING database.py
COPY database.py .
COPY api/ ./api/
COPY workers/ ./workers/
COPY utils/ ./utils/
COPY templates/ ./templates/

# Copy MCP server code (for STDIO transport)
# Note: programs.db is mounted as volume, don't copy it
COPY mcp_server/__init__.py ./mcp_server/
COPY mcp_server/server.py ./mcp_server/

# Copy entrypoint script for MCP setup
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Create necessary directories
RUN mkdir -p /app/outputs /app/logs /app/mcp /app/mcp_server /root/.config/claude

# Expose FastAPI port
EXPOSE 8000

# Set PYTHONPATH for absolute imports
ENV PYTHONPATH=/app

# Use entrypoint script for MCP setup
ENTRYPOINT ["docker-entrypoint.sh"]

# Default command (run FastAPI server)
CMD ["python", "-m", "api.server"]
