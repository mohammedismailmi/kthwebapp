FROM python:3.11-slim

# Create user with UID 1000 for Hugging Face Spaces security standards
RUN useradd -m -u 1000 user

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY --chown=user:user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY --chown=user:user . .

# Ensure directory permissions for database and uploads
RUN mkdir -p uploads data static && chown -R user:user /app && chmod -R 777 /app

USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

# Expose port 7860 (HF Spaces default)
EXPOSE 7860

# Run the FastAPI server (uses PORT env var if provided by Render, fallback to 7860)
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT:-7860}"]

