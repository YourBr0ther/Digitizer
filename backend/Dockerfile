FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg lsdvd dvdbackup eject \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY digitizer/ digitizer/

RUN mkdir -p /data /output/dvd /output/vhs && \
    addgroup --system --gid 1001 digitizer && \
    adduser --system --uid 1001 --gid 1001 digitizer && \
    chown -R digitizer:digitizer /app /data /output

USER digitizer

CMD ["uvicorn", "digitizer.main:app_factory", "--host", "0.0.0.0", "--port", "8000", "--factory"]
