FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    libxcb1 \
    libxcb-shm0 \
    libxcb-render0 \
    libgl1 \
    libglib2.0-0 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
