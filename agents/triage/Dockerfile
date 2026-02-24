# Triage Agent: consume ticket.created, produce ticket.triaged
# Build from repo root: docker build -f agents/triage/Dockerfile .
FROM python:3.12-slim

WORKDIR /app

COPY agents/triage/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY agents/triage/triage/ ./triage/

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENTRYPOINT ["python", "-m", "triage"]
