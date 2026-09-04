# --- Stage 1: Build stage ---
FROM python:3.9-slim AS builder

WORKDIR /app

# تثبيت الأدوات اللازمة لبناء الحزم إذا لزم الأمر
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# تثبيت المكتبات في مسار محلي خاص بالمستخدم لتقليل حجم الصورة النهائية
RUN pip install --no-cache-dir --user -r requirements.txt

# --- Stage 2: Production stage ---
FROM python:3.9-slim

WORKDIR /app


COPY --from=builder /root/.local /root/.local

COPY . .


ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1

EXPOSE 5000


HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/').read()"


CMD ["python", "app.py"]