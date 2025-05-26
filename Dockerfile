FROM --platform=linux/amd64 python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    libc6-dev \
    sqlite3 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV LLMWARE_DISABLE_MEMORY_MAPPING=1
ENV OMP_NUM_THREADS=1
ENV PYTHONPATH=/app
ENV LLMWARE_DATA_PATH=/app/data
ENV TOKENIZERS_PARALLELISM=false
ENV MKL_NUM_THREADS=1
ENV OPENBLAS_NUM_THREADS=1
ENV VECLIB_MAXIMUM_THREADS=1
ENV NUMEXPR_NUM_THREADS=1

# Create necessary directories with proper permissions
RUN mkdir -p /app/data \
    && mkdir -p /app/data/my_csv_folder \
    && mkdir -p /app/data/sqlite \
    && mkdir -p /usr/local/lib/python3.10/site-packages/llmware/lib/gguf/gguf_linux_x86 \
    && mkdir -p /usr/local/lib/python3.10/site-packages/llmware/lib/gguf/gguf_linux_aarch64 \
    && chmod -R 777 /app/data

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set proper permissions for application files
RUN chown -R root:root /app && \
    chmod -R 755 /app

# Expose port
EXPOSE 80

# Initialize database and start application
CMD ["sh", "-c", "python -c 'from app.config.llm_config import initialize_database; initialize_database()' && uvicorn app.main:app --host 0.0.0.0 --port 80"]