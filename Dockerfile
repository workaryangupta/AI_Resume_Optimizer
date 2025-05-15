# Use a slim Python base
FROM python:3.11-slim

WORKDIR /app

# 1) Copy & install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2) Copy your app code & font
COPY app.py DejaVuSans.ttf ./

# 3) Tell Cloud Run which port
ENV PORT=8080

# 4) Launch via Gunicorn
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8080", "--workers", "1"]
