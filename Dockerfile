FROM python:3.12-slim

LABEL maintainer="AgentShield Team"
LABEL description="AgentShield V3 - Behavior-chain risk governance for multi-agent systems"

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Expose the standalone API port (app.py)
EXPOSE 8090

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8090/health')" || exit 1

# Run the standalone entry point
CMD ["python", "backend/app.py"]
