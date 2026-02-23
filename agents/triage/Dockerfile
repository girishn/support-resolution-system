# Triage Agent: consume ticket.created, produce ticket.triaged
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY triage/ ./triage/

ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "-m", "triage"]
