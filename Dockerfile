FROM python:3.11-slim

WORKDIR /app

COPY requirements-server.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements-server.txt

COPY backend/ backend/

RUN mkdir -p backend/uploads/evidence backend/uploads/worker_photos backend/uploads/clips backend/uploads/stream

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
