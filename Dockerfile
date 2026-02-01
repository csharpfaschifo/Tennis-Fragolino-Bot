FROM python:3.11-slim

# Install system deps
RUN apt-get update && \
    apt-get install -y tesseract-ocr tesseract-ocr-eng tesseract-ocr-ita && \
    rm -rf /var/lib/apt/lists/*

# Set workdir
WORKDIR /app

# Install python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

# Expose port (Render uses $PORT)
EXPOSE 10000

# Start bot
CMD ["python", "bot.py"]
