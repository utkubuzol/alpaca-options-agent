# Build context = repo root:  docker build -f web/backend/Dockerfile -t saas-api .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

WORKDIR /app

# Root agent package (strategy / risk / execution / broker) + its deps
COPY pyproject.toml requirements.txt README.md ./
COPY alpaca_options_agent ./alpaca_options_agent
RUN pip install -r requirements.txt && pip install -e .

# Backend service
COPY web/backend/requirements.txt ./web/backend/requirements.txt
RUN pip install -r web/backend/requirements.txt
COPY web/backend ./web/backend

WORKDIR /app/web/backend
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
