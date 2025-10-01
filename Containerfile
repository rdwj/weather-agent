# Multi-stage build for production optimization
FROM registry.redhat.io/ubi9/python-311:latest AS builder

# Set working directory
WORKDIR /opt/app-root/src

# Copy requirements files
COPY requirements.txt requirements-dev.txt ./

# Install build dependencies
USER 0
RUN dnf install -y gcc python3-devel && \
    dnf clean all

USER 1001

# Create virtual environment and install dependencies
RUN python -m venv /opt/app-root/venv && \
    . /opt/app-root/venv/bin/activate && \
    pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Production stage
FROM registry.redhat.io/ubi9/python-311:latest

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/app-root/venv/bin:$PATH" \
    PYTHONPATH="/opt/app-root/src:$PYTHONPATH"

# Create app directory
WORKDIR /opt/app-root/src

# Copy virtual environment from builder
COPY --from=builder /opt/app-root/venv /opt/app-root/venv

# Copy application code
COPY src/ ./src/
COPY ui/ ./ui/
COPY prompts/ ./prompts/

# Create non-root user (if not already created)
USER 1001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health')" || exit 1

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "src.api.weather_api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]