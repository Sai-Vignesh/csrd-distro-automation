FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

WORKDIR /app

# Copy the project files
COPY . .

# Install Python dependencies
# We install gunicorn to serve the Flask app in production
RUN pip install --no-cache-dir gunicorn
RUN pip install --no-cache-dir .

# Install Playwright browser and its Linux system dependencies
RUN playwright install chromium
RUN playwright install-deps chromium

# Run the web service on container startup using gunicorn
# 1 worker with 8 threads handles the web requests
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 src.web.app:app
