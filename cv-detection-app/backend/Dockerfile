FROM python:3.11-slim

WORKDIR /app

# Install system deps required by some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    v4l-utils \
    libavdevice-dev \
    libsm6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

# Copy backend sources and install requirements
COPY . /app
WORKDIR /app/backend

RUN python -m pip install --upgrade pip
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt || true; fi
# Ensure minimal runtime deps are present (install explicitly to avoid silent failures)
RUN pip install --no-cache-dir httpx fastapi python-dotenv uvicorn python-multipart pillow opencv-python

EXPOSE 8080

ENV PYTHONUNBUFFERED=1

# Default command: run uvicorn to serve the FastAPI app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
