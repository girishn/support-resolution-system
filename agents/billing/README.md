# Billing Agent

Consumes `ticket.triaged` events from the `ticket.triaged.billing` Kafka topic, generates a draft support response using an LLM, and produces `ticket.resolved` events to the `ticket.resolved` topic.

## Behavior

- **Input**: Messages on `ticket.triaged.billing` with `event_type: "ticket.triaged"` (from the Triage agent; payload matches [ticket.triaged schema](../../events/ticket.triaged.schema.json)).
- **Output**: Messages on `ticket.resolved` with `event_type: "ticket.resolved"` (payload matches [ticket.resolved schema](../../events/ticket.resolved.schema.json)). Includes a `response` field with the draft reply and `resolved_by: "billing"`.

## Environment variables

| Variable                  | Required | Description                                                                 |
| ------------------------- | -------- | --------------------------------------------------------------------------- |
| `KAFKA_BOOTSTRAP_SERVERS` | Yes      | e.g. `kafka.confluent.local:9092`                                          |
| `LLM_PROVIDER`            | No       | `anthropic` (default), `openai`, or `ollama`                                |
| `ANTHROPIC_API_KEY`       | Yes*     | For Anthropic (Claude). Required when `LLM_PROVIDER=anthropic`             |
| `OPENAI_API_KEY`          | Yes*     | Required when `LLM_PROVIDER=openai`                                       |
| `OLLAMA_BASE_URL`         | No       | When `LLM_PROVIDER=ollama`, e.g. `http://ollama.support-agents.svc:11434/v1` |
| `OLLAMA_MODEL`            | No       | Model name (default `llama3.2`)                                             |
| `LOG_LEVEL`               | No       | Default `INFO`                                                              |
| `MOCK_LLM`                | No       | Set to `1` or `true` for fixed response (e2e/CI without API credits)       |
| `LOG_FORMAT`              | No       | `json` (default) or `console`                                               |
| `METRICS_PORT`            | No       | Prometheus metrics HTTP port (default `9091`)                               |

## Run locally

Kafka must be reachable (see [triage agent](../triage/README.md) for VPC/DNS notes).

```bash
cd agents/billing
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
set KAFKA_BOOTSTRAP_SERVERS=kafka.confluent.local:9092
python -m billing
```

## Run in Kubernetes

See [k8s/README.md](k8s/README.md) for build, push, and deploy steps. Uses the same namespace (`support-agents`) and can share Ollama with the triage agent.
