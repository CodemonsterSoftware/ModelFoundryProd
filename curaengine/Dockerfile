FROM ubuntu:22.04

# Install dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    python3 \
    python3-pip \
    libglib2.0-dev \
    ninja-build

# Install Python dependencies
RUN pip3 install flask gunicorn requests

# Clone and build CuraEngine
WORKDIR /opt
RUN git clone https://github.com/Ultimaker/CuraEngine.git
WORKDIR /opt/CuraEngine
RUN git checkout master
RUN mkdir build && cd build && cmake .. && make -j4

# Create directory for configuration files
WORKDIR /app
RUN mkdir -p /app/data/profiles

# Copy resource files (will be added later)
COPY resources /app/resources/

# Copy API server script
COPY api.py /app/

# Expose port for API
EXPOSE 8080

# Run the API server
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "api:app"] 