FROM python:3.12-slim

# Set the working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Generate build version
ARG VERSION=$(date +"%Y%m%d%H%M")
ENV VERSION=$VERSION

# Add a build argument for the environment with default as production
ARG ENVIRONMENT=development
ENV ENVIRONMENT=$ENVIRONMENT

# Copy application files
COPY . /app/

# Handle environment files based on branch/environment
RUN if [ "$ENVIRONMENT" = "development" ]; then \
        echo "Using development environment" && \
        cp /app/.dev.env /app/.env && \
        echo "Development .env file:" && \
        cat /app/.env; \
    elif [ "$ENVIRONMENT" = "production" ]; then \
        echo "Using production environment" && \
        echo "Production .env file:" && \
        cat /app/.env; \
    else \
        echo "Environment not specified correctly" && \
        exit 1; \
    fi

# Install system-level dependencies
RUN apt-get update && apt-get install -y procps redis-server libreoffice

# Expose necessary ports
EXPOSE 80 443 5000

# Make the startup script executable
RUN chmod +x /app/startprod.sh

# Set environment variables needed by Flask
ENV PORT=80
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=80
ENV PYTHONPATH=/app

# Create and set permissions for log directory
RUN mkdir -p /home/LogFiles \
    && touch /home/LogFiles/app.log \
    && chmod 777 /home/LogFiles/app.log

# Create a wrapper script to load environment variables and start the application
RUN echo '#!/bin/sh\n\
set -e\n\
echo "Current environment: $ENVIRONMENT"\n\
echo "Loading environment variables from .env file"\n\
set -a\n\
. /app/.env\n\
set +a\n\
echo "Starting Flask application"\n\
exec python -m flask run --host=0.0.0.0 --port=80\n\
' > /app/start.sh \
&& chmod +x /app/start.sh

CMD ["/bin/sh", "/app/start.sh"]