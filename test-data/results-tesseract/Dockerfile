FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng tesseract-ocr-rus python3 ca-certificates curl && rm -rf /var/lib/apt/lists/*
ENV OMP_THREAD_LIMIT=1
