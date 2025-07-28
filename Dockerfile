# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
  gcc \
  g++ \
  && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the Python script
COPY pdf_outline_extractor.py .

# Create input and output directories
RUN mkdir -p /app/input /app/output

# Set the default command to run the script
CMD ["python", "pdf_outline_extractor.py"]
