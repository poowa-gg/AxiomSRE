# Dockerfile for AxiomSRE
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Run test suite to verify image build integrity
RUN python -m pytest tests/ -v

EXPOSE 8000

CMD ["python", "main.py"]
