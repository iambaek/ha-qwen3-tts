FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Set cache directories to /data for persistence
ENV HF_HOME=/data/hf_cache
ENV TORCH_HOME=/data/torch_cache
# Reduce glibc malloc arena count to lower memory fragmentation
ENV MALLOC_ARENA_MAX=2

WORKDIR /app

# Install torch + torchaudio
# amd64: use PyTorch CPU-only wheel index (smaller, no CUDA)
# aarch64: CPU wheel index has no ARM builds — fall back to PyPI
RUN ARCH="$(uname -m)" && \
    if [ "$ARCH" = "x86_64" ]; then \
        pip install --no-cache-dir torch torchaudio \
            --index-url https://download.pytorch.org/whl/cpu; \
    else \
        echo "Detected arch=$ARCH, installing torch from PyPI" && \
        pip install --no-cache-dir torch torchaudio; \
    fi

# Install remaining dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .
COPY run.sh .
RUN chmod +x /app/run.sh

EXPOSE 5000

CMD ["/app/run.sh"]
