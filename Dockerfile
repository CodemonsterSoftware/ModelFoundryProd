# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
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

# Set up database
RUN touch /app/db/db.sqlite3 \
    && chmod 666 /app/db/db.sqlite3

# Collect static files
RUN python manage.py collectstatic --noinput

# Run migrations and initialize materials
RUN python manage.py migrate && \
    python manage.py init_materials

# Expose port 8000
EXPOSE 8000

# Command to run the application with host binding
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000", "--noreload"] 