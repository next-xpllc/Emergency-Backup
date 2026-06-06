FROM python:3.11-slim

WORKDIR /app

# System deps for tls_client and curl_cffi native builds
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Railway injects PORT env var; autorz.py already reads it
ENV PORT=8000

EXPOSE $PORT

CMD ["sh", "entrypoint.sh"]
