FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (leverage Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code 
# Note: credentials.json and token.json are EXCLUDED (injected via Railway env vars)
COPY server.py .
COPY auth/ auth/
COPY tools/ tools/
COPY resources/ resources/
COPY prompts/ prompts/
COPY utils/ utils/

# Copy and configure startup script
COPY start.sh .
RUN chmod +x start.sh

# The actual port is injected by Railway at runtime via $PORT
EXPOSE 8000

CMD ["./start.sh"]
