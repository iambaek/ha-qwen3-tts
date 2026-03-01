FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Set cache directories to /data for persistence
ENV HF_HOME=/data/hf_cache
ENV TORCH_HOME=/data/torch_cache

WORKDIR /app

# Install torch + torchaudio (CPU-only wheels) separately first for layer caching
# torchaudio must be pre-installed from the CPU index before qwen_tts pulls it in
RUN pip install --no-cache-dir \
    torch torchaudio --index-url https://download.pytorch.org/whl/cpu

# Install remaining dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .
COPY run.sh .
RUN chmod +x /app/run.sh

EXPOSE 5000

CMD ["/app/run.sh"]
