# Technical Agent: consume ticket.triaged.technical, produce ticket.resolved
FROM python:3.12-slim

WORKDIR /app

COPY agents/technical/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ ./shared/
COPY agents/technical/technical/ ./technical/

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENTRYPOINT ["python", "-m", "technical"]
