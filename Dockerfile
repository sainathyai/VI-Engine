FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (layer-cached)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY vi_engine/ ./vi_engine/

# Runtime directories (mounted as volumes in production)
RUN mkdir -p outputs/substack/drafts outputs/substack/posts

ENV PYTHONUNBUFFERED=1

# Default: run the dashboard (override CMD for the collection job)
EXPOSE 8000
CMD ["uvicorn", "vi_engine.dashboard.app:app", "--host", "0.0.0.0", "--port", "8000"]
