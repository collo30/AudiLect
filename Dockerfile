# Use official slim Python runtime
FROM python:3.10-slim

# Install system media dependencies (FFmpeg for audio & libgl for OpenCV slide hashing)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /app

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Hugging Face Spaces default port is 7860
EXPOSE 7860
ENV PORT=7860
ENV SPACE_ID=huggingface

# Launch AudiLect Cockpit
CMD ["python", "run.py", "--host", "0.0.0.0", "--port", "7860"]
