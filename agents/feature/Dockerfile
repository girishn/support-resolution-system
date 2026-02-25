# Feature Agent: consume ticket.triaged.feature_request, produce ticket.resolved
FROM python:3.12-slim

WORKDIR /app

COPY agents/feature/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY agents/feature/feature/ ./feature/

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENTRYPOINT ["python", "-m", "feature"]
