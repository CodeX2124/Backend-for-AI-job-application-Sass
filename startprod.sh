#!/bin/bash

# Function to handle Ctrl-C
cleanup() {
    echo "Ctrl-C detected. Shutting down..."
    kill $FLOWER_PID
    kill $WORKER_PID
    kill $BEAT_PID
    kill $FLASK_PID
    return 1
}

# Function to start Redis if not already running
start_redis() {
    if ! pgrep -x "redis-server" > /dev/null; then
        echo "Starting Redis..."
        redis-server --daemonize yes
        sleep 2  # Give Redis some time to start
    else
        echo "Redis is already running."
    fi
}

# Start Redis
start_redis


# Set up trap to call cleanup function when SIGINT is received
trap cleanup SIGINT

# Start Flower in the background
celery -A app.celery_app.celery flower --FLOWER_UNAUTHENTICATED_API &
FLOWER_PID=$!

# Start Celery worker in the background
celery -A app.celery_app.celery worker --loglevel=info &
WORKER_PID=$!

# Start Beat worker in the background
celery -A app.celery_app.celery beat --loglevel=info &
BEAT_PID=$!

flask run &
FLASK_PID=$!

# Wait for both processes
wait $FLOWER_PID $WORKER_PID $BEAT_PID $FLASK_PID
