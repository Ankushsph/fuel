# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies required for OpenCV and other packages
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Make startup script executable
RUN chmod +x start.sh

# Create uploads directory
RUN mkdir -p uploads/receipts uploads/payment_proofs uploads/pump_documents

# Expose port (Railway uses PORT env variable)
EXPOSE 8080

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV FLASK_APP=app.py

# Run startup script (includes migrations + gunicorn)
CMD ["bash", "start.sh"]

