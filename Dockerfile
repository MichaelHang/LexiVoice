FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY app.py .
COPY templates/ ./templates/
COPY static/ ./static/

# Create directories for audio files
RUN mkdir -p generated_audio temp_files

# Expose port
EXPOSE 8080

# Run with gunicorn
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8080", "--timeout", "300", "app:app"]
