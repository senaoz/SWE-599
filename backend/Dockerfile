FROM python:3.10-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY research/src/ ./research/src/
COPY research/requirements.txt ./research/requirements.txt
RUN pip install --no-cache-dir rank-bm25 google-generativeai

ENV PYTHONPATH=/app

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8001"]
