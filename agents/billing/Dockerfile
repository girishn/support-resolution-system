# Billing Agent: consume ticket.triaged.billing, produce ticket.resolved
FROM python:3.12-slim

WORKDIR /app

COPY agents/billing/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY agents/billing/billing/ ./billing/

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENTRYPOINT ["python", "-m", "billing"]
