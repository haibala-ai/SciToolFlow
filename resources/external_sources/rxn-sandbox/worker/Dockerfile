FROM public.ecr.aws/docker/library/python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies (only what you actually need)
RUN apt-get update \
    && apt-get install -y \
        libexpat1 \
        libxrender1 \
        libxext6 \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency definitions first (for cache friendliness)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Ensure entrypoint is executable
RUN chmod +x start.sh

# Change to non-root user
RUN useradd -m -u 1000 rxn && \
    chown -R rxn:rxn /app

USER rxn

ENTRYPOINT ["./start.sh"]
