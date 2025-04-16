# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=modelfoundry.settings
ENV DJANGO_ALLOWED_HOSTS=*

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Clone the repository
RUN git clone https://github.com/CodemonsterSoftware/ModelFoundryProd.git /app

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create necessary directories with proper permissions
RUN mkdir -p /app/media /app/staticfiles /app/db \
    && chmod -R 777 /app/media /app/staticfiles /app/db

# Create startup script
RUN echo '#!/bin/bash\n\
python manage.py migrate --noinput\n\
python manage.py init_materials\n\
python manage.py collectstatic --noinput\n\
python manage.py runserver 0.0.0.0:8000 --noreload' > /app/start.sh \
&& chmod +x /app/start.sh

# Expose port 8000
EXPOSE 8000

# Command to run the application
CMD ["/app/start.sh"] 