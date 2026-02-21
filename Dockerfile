FROM python:3.11-slim

# Install system dependencies for OpenCV headless
RUN apt-get update && apt-get install -y \
    libxcb1 \
    libxcb-shm0 \
    libxcb-render0 \
    libgl1-mesa-glx \
    libglib2.0-0 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app
COPY . .

# Expose Streamlit port
EXPOSE 8080

# Run Streamlit
CMD ["streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0"]
