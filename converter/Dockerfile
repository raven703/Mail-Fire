FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends libreoffice-writer libreoffice-calc libreoffice-impress fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
WORKDIR /service
COPY server.py validation.py ./
USER 10001:10001
CMD ["python", "server.py"]