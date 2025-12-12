# Old 'buster' image removed. Using newer 'bookworm' (Debian 12)
FROM python:3.11-slim-bookworm

# Set Environment Variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install System Dependencies
RUN apt-get update && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends git curl \
    && rm -rf /var/lib/apt/lists/*

# Set Working Directory
WORKDIR /app

# Copy Requirements First (For Docker Caching)
COPY requirements.txt .

# Install Python Dependencies
RUN pip3 install --no-cache-dir -U pip \
    && pip3 install --no-cache-dir -U -r requirements.txt

# Copy Project Files
COPY . .

# Grant Permission to Start Script (Optional but safe)
RUN chmod +x start.sh

# Run the Bot
CMD ["bash", "start.sh"]
