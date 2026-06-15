# ── Meridian backend — FastAPI + C++ extensions ──────────────────
FROM python:3.12-slim

# System deps: g++ for the pybind11 C++ build
RUN apt-get update && apt-get install -y --no-install-recommends \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

# Copy the backend source
COPY . .

# Build the C++ extensions (greeks_module + quant_module)
RUN python setup.py build_ext --inplace

# Railway provides $PORT at runtime; default to 8000 locally
ENV PORT=8000
EXPOSE 8000

# Start the server. Single worker — required because the WebSocket feeds
# and scheduler must run in exactly one process (see note in README).
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT} --workers 1
