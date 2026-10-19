FROM public.ecr.aws/docker/library/python:3.13-slim

# Prevents interactive prompts during apt install
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies required by RDKit and matplotlib
RUN apt-get update && apt-get install -y \
    build-essential \
    libxrender1 \
    libxext6 \
    libsm6 \
    libglib2.0-0 \
    libgl1 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /rxn

# Copy and install Python dependencies
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["jupyter", "notebook", \
     "--ip=0.0.0.0", \
     "--port=8888", \
     "--no-browser", \
     "--ServerApp.allow_root=True", \
     "--IdentityProvider.token=", \
     "--ServerApp.password=", \
     "--ServerApp.default_url=/notebook.ipynb"]