FROM python:3.9-slim

# Create log directory with appropriate permissions
RUN mkdir -p /var/log/auto-hpa && chmod 755 /var/log/auto-hpa

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ /app/src/
CMD ["kopf", "run", "--standalone", "/app/src/controller.py"]
