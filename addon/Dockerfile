FROM python:3.11-slim

# Install system dependencies
# - libsndfile1 : soundfile
# - libgomp1   : OpenMP runtime required by torchaudio
# - sox        : optional audio utility used by some torchaudio backends
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    libgomp1 \
    sox \
    && rm -rf /var/lib/apt/lists/*

# Set cache directories to /data for persistence
ENV HF_HOME=/data/hf_cache
ENV TORCH_HOME=/data/torch_cache
# Reduce glibc malloc arena count to lower memory fragmentation
ENV MALLOC_ARENA_MAX=2

WORKDIR /app

# Pin torch to 2.2.2 — aarch64 compatible (Cortex-A72/A76, no SVE required).
# torch 2.5+ is compiled with SVE/other extensions not available on RPi 4/5,
# causing SIGILL ("Illegal instruction") on import.
#
# amd64 : use PyTorch CPU-only wheel index (no CUDA, smaller)
# aarch64: use PyPI (CPU wheel index has no ARM builds)
RUN ARCH="$(uname -m)" && \
    echo "Building for arch: $ARCH" && \
    if [ "$ARCH" = "x86_64" ]; then \
        pip install --no-cache-dir "torch==2.2.2" "torchaudio==2.2.2" \
            --index-url https://download.pytorch.org/whl/cpu; \
    else \
        pip install --no-cache-dir "torch==2.2.2" "torchaudio==2.2.2"; \
    fi

# Write pip constraints:
# - torch/torchaudio pinned so qwen_tts cannot upgrade to an incompatible version
# - numpy<2 required because torch 2.2.2 was built against NumPy 1.x
RUN echo "torch==2.2.2"    >  /tmp/constraints.txt && \
    echo "torchaudio==2.2.2" >> /tmp/constraints.txt && \
    echo "numpy<2"           >> /tmp/constraints.txt

# Pre-install numpy<2 before requirements.txt so it is already satisfied
RUN pip install --no-cache-dir "numpy<2"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -c /tmp/constraints.txt

COPY server.py .
COPY run.sh .
RUN chmod +x /app/run.sh

EXPOSE 5000

CMD ["/app/run.sh"]
