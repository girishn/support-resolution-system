# Triage Agent

Consumes `ticket.created` events from the `ticket.events` Kafka topic, optionally enriches with customer data from DynamoDB, classifies each ticket using an LLM (type + priority + reasoning), and produces `ticket.triaged` events to **type-specific topics** for downstream specialist agents (Billing, Technical, Feature).

## Behavior

- **Input**: Messages on `ticket.events` with `event_type: "ticket.created"` (payload matches [ticket.created schema](../../events/ticket.created.schema.json)).
- **Enrichment** (optional): When `DYNAMODB_TABLE` is set, fetches customer by `customer_id` and merges into the payload.
- **Output**: Produces to type-specific topics based on classification:
  - `ticket.triaged.billing` → Billing agent
  - `ticket.triaged.technical` → Technical agent
  - `ticket.triaged.feature_request` → Feature agent
  - `ticket.triaged.account`, `ticket.triaged.other` → (future agents)
  Payload matches [ticket.triaged schema](../../events/ticket.triaged.schema.json). Includes a `customer` field when enrichment succeeds.
- **Partitioning**: Messages are keyed by `ticket_id` so all events for a ticket stay in order.

## Environment variables


| Variable                  | Required    | Description                                                                                                                                                                                       |
| ------------------------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `KAFKA_BOOTSTRAP_SERVERS` | Yes         | e.g. `kafka.confluent.local:9092`                                                                                                                                                                 |
| `KAFKA_TOPIC`             | No          | Default `ticket.events`                                                                                                                                                                           |
| `ANTHROPIC_API_KEY`       | Yes*        | For classification (default provider)                                                                                                                                                             |
| `OPENAI_API_KEY`          | Yes*        | If `LLM_PROVIDER=openai`                                                                                                                                                                          |
| `LLM_PROVIDER`            | No          | `anthropic` (default), `openai`, or `ollama`                                                                                                                                                      |
| `OLLAMA_BASE_URL`         | No (ollama) | When `LLM_PROVIDER=ollama`, API base URL (default `http://localhost:11434/v1`). From in-cluster pods use a URL the cluster can reach (e.g. deploy Ollama in-cluster or tunnel from your machine). |
| `OLLAMA_MODEL`            | No (ollama) | Model name (default `llama3.2`). Use any model you have in Ollama (e.g. `mistral`, `llama3.2`).                                                                                                   |
| `LOG_LEVEL`               | No          | Default `INFO`                                                                                                                                                                                    |
| `MOCK_LLM`                | No          | Set to `1` or `true` to skip real LLM calls and return a fixed triage (for e2e/CI when API credits are unavailable).                                                                              |
| `DYNAMODB_TABLE`          | No          | DynamoDB table name for customer enrichment. When set, the agent fetches customer by `customer_id` and adds a `customer` field to `ticket.triaged`. Pod needs IAM read access.                   |
| `LOG_FORMAT`             | No          | `json` (default in k8s) for structured logs, or `console` for dev.                                                                                                                              |
| `METRICS_PORT`           | No          | Prometheus metrics HTTP port (default `9090`). Exposes `/metrics`.                                                                                                                               |


## Run locally

**Kafka must be reachable.** The bootstrap and broker hostnames (`kafka.confluent.local`, `b0.confluent.local`, etc.) only resolve inside the same VPC (Route 53 private zone). Port-forwarding the bootstrap alone is not enough—Kafka returns broker addresses in metadata, so the client also needs to reach `b0`/`b1`/`b2`, which won’t resolve on your laptop. From a machine outside the VPC you should **run the agent inside the cluster** (Deployment on the same EKS cluster as Kafka) so it uses in-cluster DNS. For local dev, use an EC2 or pod in the VPC, or VPN/bastion so your machine can resolve and reach those hostnames.

1. Create a venv and install deps:
  ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   # source .venv/bin/activate  # Linux/macOS
   pip install -r requirements.txt
  ```
2. Set env (e.g. in `.env` or shell):
  ```bash
   set KAFKA_BOOTSTRAP_SERVERS=kafka.confluent.local:9092
   set ANTHROPIC_API_KEY=sk-ant-...
  ```
3. Run:
  ```bash
   python -m triage
  ```

**Using Ollama locally:** Install [Ollama](https://ollama.com), pull a model (e.g. `ollama pull llama3.2`), then run the agent on the same machine with:

   Kafka must still be reachable from that machine (see note above). To use Ollama with the agent running in Kubernetes, either deploy Ollama in the cluster and set `OLLAMA_BASE_URL` to its service URL, or expose your local Ollama to the cluster (e.g. via a tunnel) and set that URL in the agent ConfigMap.

## Run in Kubernetes (same cluster as Kafka)

Running the agent in the same EKS cluster as Kafka lets it resolve `kafka.confluent.local` and `b0`/`b1`/`b2` and connect without port-forward.

1. **Build and push the image** (from repo root; build context must include `shared/`):
   ```bash
   docker build -f agents/triage/Dockerfile -t triage-agent:latest .
  export AWS_REGION=us-east-1
  aws ecr create-repository --repository-name triage-agent --region $AWS_REGION 2>/dev/null || true
  aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin 766198264464.dkr.ecr.us-east-1.amazonaws.com
   # Tag and push to your registry (e.g. ECR):
  docker tag triage-agent:latest 766198264464.dkr.ecr.us-east-1.amazonaws.com/triage-agent:latest
  docker push 766198264464.dkr.ecr.us-east-1.amazonaws.com/triage-agent:latest
  ```
2. **Apply manifests** (see [k8s/README.md](k8s/README.md) for full steps):
  ```bash
   kubectl apply -f k8s/namespace.yaml
   kubectl apply -f k8s/configmap.yaml
   kubectl create secret generic triage-agent-keys -n support-agents --from-literal=ANTHROPIC_API_KEY=sk-ant-...
   # Edit k8s/deployment.yaml and set the image to your pushed image, then:
   kubectl apply -f k8s/deployment.yaml
  ```
3. **Verify**: `kubectl get pods -n support-agents -l app=triage-agent` and `kubectl logs -n support-agents -l app=triage-agent -f`.
4. **E2E test**: From repo root run `./scripts/e2e-triage.sh` to produce a test ticket and assert a `ticket.triaged` event is produced (see [k8s/README.md](k8s/README.md)).

Full details, ECR example, and file descriptions: **[agents/triage/k8s/README.md](k8s/README.md)**.

## Message format

- **Input** (`ticket.events`): `{"event_type": "ticket.created", "ticket_id": "...", "customer_id": "...", "subject": "...", "body": "...", "created_at": "...", "channel": "portal"}`
- **Output** (type-specific topics, e.g. `ticket.triaged.billing`): `{"event_type": "ticket.triaged", "ticket_id": "...", "customer_id": "...", "type": "billing", "priority": "high", "triaged_at": "...", "reasoning": "...", "original_subject": "...", "body": "..."}`

