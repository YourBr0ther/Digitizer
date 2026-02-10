FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg lsdvd dvdbackup eject \
    libgl1-mesa-glx libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY digitizer/ digitizer/

RUN mkdir -p /data /output/dvd /output/vhs

CMD ["uvicorn", "digitizer.main:app", "--host", "0.0.0.0", "--port", "8000", "--factory"]
