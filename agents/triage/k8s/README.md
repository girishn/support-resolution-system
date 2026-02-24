# Triage Agent – Kubernetes

Manifests to run the Triage Agent on the same EKS cluster as Kafka so `kafka.confluent.local` and broker hostnames resolve.

## Prerequisites

- `kubectl` context set to the EKS cluster where Kafka runs (e.g. terraform-aws-confluent-platform).
- Kafka and DNS already set up (`kafka.confluent.local`, `b0`/`b1`/`b2` resolving in the VPC).
- Container image for the agent (built and pushed to a registry the cluster can pull from).

**Optional – in-cluster LLM (no API keys):** Deploy Ollama in the cluster and use it as the triage LLM. See [Ollama in-cluster](#ollama-in-cluster) below.

## Steps

### 1. Build and push the image

From **support-resolution-system** repo root (build context must include `shared/`):

```bash
# Example: AWS ECR in us-east-1. Replace with your region/account.
export AWS_REGION=us-east-1
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
ECR_URI="${ECR_REGISTRY}/triage-agent:latest"

# Create repo if missing:
# aws ecr create-repository --repository-name triage-agent --region $AWS_REGION

aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REGISTRY

docker build -f agents/triage/Dockerfile -t triage-agent:latest .
docker tag triage-agent:latest $ECR_URI
docker push $ECR_URI
```

### 2. Create namespace, service account, and config

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/serviceaccount.yaml
kubectl apply -f k8s/configmap.yaml
```

The `triage-agent` ServiceAccount is used with EKS Pod Identity when the agent accesses DynamoDB (see [DynamoDB enrichment](#dynamodb-enrichment) below).

**Ollama in-cluster (free, no API key):** To use Ollama as the LLM inside the cluster (so pods can reach it without exposing your laptop):

1. Deploy Ollama and pull a model (same namespace as the agent):
   ```bash
   kubectl apply -f k8s/ollama.yaml
   # Wait for the pod to be ready; the default model (qwen2.5:0.5b) is pulled in the background (~1–2 min). Check: kubectl logs -n support-agents -l app=ollama -f
   ```
2. Point the triage agent at it: in `k8s/configmap.yaml` set `LLM_PROVIDER: "ollama"`, `OLLAMA_BASE_URL: "http://ollama.support-agents.svc:11434/v1"`, and `OLLAMA_MODEL: "qwen2.5:0.5b"` (already set if you use the repo default).
3. Apply the ConfigMap and restart the agent:
   ```bash
   kubectl apply -f k8s/configmap.yaml
   kubectl rollout restart deployment/triage-agent -n support-agents
   ```
4. To use a different model (e.g. `phi`, `llama3.2`): ensure the node has enough memory (~2Gi for phi), then `kubectl exec -n support-agents deploy/ollama -- ollama pull <model>` and set `OLLAMA_MODEL` in the ConfigMap.

#### Ollama in-cluster

The `ollama.yaml` manifest runs the official [ollama/ollama](https://hub.docker.com/r/ollama/ollama) image (CPU-only). It is sized for **t3.medium** nodes with tight memory: uses **qwen2.5:0.5b** (~400MB) so it fits in ~600MiB available. Models are stored on a PVC so they persist across restarts. The triage agent ConfigMap uses `OLLAMA_MODEL=qwen2.5:0.5b` by default.

If the pod fails to schedule (e.g. "didn't match PersistentVolume's node affinity" or "Insufficient memory"): the existing PVC may be bound to a node that no longer has enough free memory. Delete the Ollama deployment and the PVC (`kubectl delete -f k8s/ollama.yaml`), then re-apply; the new PVC will bind to a node with capacity and the default model will be pulled on first start.

If the triage agent logs **"model '...' not found"**: the model may not be pulled yet (postStart runs in background). Pull it manually: `kubectl exec -n support-agents deploy/ollama -- ollama pull qwen2.5:0.5b` (or the model name in the error), then retry.

Edit `k8s/configmap.yaml` if your Kafka bootstrap is not `kafka.confluent.local:9092`.

#### DynamoDB enrichment

To enrich tickets with customer data from DynamoDB:

1. **Apply support-resolution-system infra** (creates DynamoDB table, VPC Gateway endpoint, IAM role, Pod Identity):
   ```bash
   cd support-resolution-system/infra
   terraform init && terraform apply
   ```
2. **Get the table name** from the output: `terraform output -raw dynamodb_table_name`
3. **Set DYNAMODB_TABLE** in `k8s/configmap.yaml` to that value, then apply the ConfigMap.
4. **Ensure** `kubectl apply -f k8s/serviceaccount.yaml` was run (the deployment uses the `triage-agent` SA for Pod Identity).

Traffic to DynamoDB stays in the VPC via the Gateway endpoint (no internet egress). To use **Ollama on your laptop** with the in-cluster agent: expose local Ollama to the cluster (e.g. [ngrok](https://ngrok.com) or [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps) for `http://localhost:11434`), then set `LLM_PROVIDER: "ollama"`, `OLLAMA_BASE_URL: "https://your-tunnel-url"`, and `OLLAMA_MODEL: "llama3.2"` in the ConfigMap.

### 3. Create the API key secret

Do **not** commit real keys. Create the secret with kubectl:

```bash
kubectl create secret generic triage-agent-keys -n support-agents \
  --from-literal=ANTHROPIC_API_KEY=sk-ant-your-key-here
```

### 4. Set the image in the Deployment

Edit `k8s/deployment.yaml` and set `spec.template.spec.containers[0].image` to your pushed image (e.g. `123456789012.dkr.ecr.us-east-1.amazonaws.com/triage-agent:latest`). The manifest has a `REPLACE_ME` placeholder. If you use the same ECR URI variable as in step 1:

```bash
# Linux/macOS
sed -i "s|REPLACE_ME|$ECR_URI|g" k8s/deployment.yaml
# Or edit deployment.yaml manually.
```

### 5. Deploy and check

```bash
kubectl apply -f k8s/deployment.yaml
kubectl get pods -n support-agents -l app=triage-agent
kubectl logs -n support-agents -l app=triage-agent -f
```

### 6. E2E test

From the **support-resolution-system** repo root, with `kubectl` context set to the same EKS cluster:

```bash
./scripts/e2e-triage.sh
```

This produces one `ticket.created` event, waits for the agent to process it, and asserts that a matching `ticket.triaged` appears on `ticket.events`. Requires the `ticket.events` topic to exist (e.g. via `scripts/create-kafka-topics.sh`).

**Without API credits:** Set `MOCK_LLM: "true"` in `k8s/configmap.yaml`, then `kubectl apply -f k8s/configmap.yaml` and restart the deployment (or delete the pod so it is recreated). The agent will return a fixed triage instead of calling Anthropic/OpenAI, so e2e passes without billing.

#### Debugging E2E failures

If e2e reports "No ticket.triaged" but you see `ticket.created` in the consumer output, the agent either didn’t process the message or failed before producing. Check in this order:

1. **Triage agent logs** – Did it consume the ticket? Did the LLM call succeed or error?
   ```bash
   kubectl logs -n support-agents -l app=triage-agent --tail=150
   ```
   Look for: `Triage ticket_id=e2e-...`, then either `Produced ticket.triaged` or an error (e.g. LLM timeout, connection refused to Ollama, produce error).

2. **Ollama (if using in-cluster Ollama)** – Is the pod ready and did it receive the request?
   ```bash
   kubectl get pods -n support-agents -l app=ollama
   kubectl logs -n support-agents -l app=ollama --tail=50
   ```
   If the model wasn’t pulled yet, wait a few minutes or run:  
   `kubectl exec -n support-agents deploy/ollama -- ollama list`

3. **Agent pod health** – Is the agent running and not restarting?
   ```bash
   kubectl get pods -n support-agents -l app=triage-agent
   kubectl describe pod -n support-agents -l app=triage-agent
   ```

4. **Re-run e2e with logs in another terminal** – In one terminal run `kubectl logs -n support-agents -l app=triage-agent -f`, in another run `./scripts/e2e-triage.sh` and watch for the ticket_id and any errors in the agent log.

5. **If you never see "Received message event_type=..."** – The agent may not be receiving the e2e message (e.g. consumer group offset already past it). Scale the triage deployment to 0 so the group has no active members, then from a pod with Kafka tools (e.g. `kubectl run kafka-client --rm -i --restart=Never -n confluent --image=confluentinc/cp-kafka:7.9.0 -- bash`): run `kafka-consumer-groups --bootstrap-server kafka.confluent.local:9092 --group triage-agent --topic ticket.events --reset-offsets --to-earliest --execute`, then scale the triage deployment back to 1.

## Files

| File | Purpose |
|------|---------|
| `namespace.yaml` | Creates `support-agents` namespace. |
| `serviceaccount.yaml` | Service account for triage agent; used with EKS Pod Identity for DynamoDB access. |
| `configmap.yaml` | `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_TOPIC`, `LLM_PROVIDER`, `LOG_LEVEL`. |
| `secret.yaml.example` | Example shape only; create real secret with `kubectl create secret generic`. |
| `deployment.yaml` | Deployment that runs the agent with env from ConfigMap + Secret. |
| `ollama.yaml` | Optional: Ollama LLM server (Deployment + Service + PVC) for in-cluster, free LLM; use with `LLM_PROVIDER=ollama`. |
