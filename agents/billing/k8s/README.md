# Billing Agent – Kubernetes

Deploy the Billing Agent to the same EKS cluster as Kafka and the Triage agent.

## Prerequisites

- Triage agent deployed and producing to `ticket.triaged.billing`
- Kafka topics created (`scripts/create-kafka-topics.sh`)
- `kubectl` context set to the EKS cluster

**Optional:** Deploy Ollama in-cluster (see [triage k8s README](../../triage/k8s/README.md)) and set `LLM_PROVIDER=ollama` in the ConfigMap.

## Steps

### 1. Build and push the image

From **support-resolution-system** repo root:

```bash
export AWS_REGION=us-east-1
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/billing-agent:latest"

aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com
aws ecr create-repository --repository-name billing-agent --region $AWS_REGION 2>/dev/null || true

docker build -f agents/billing/Dockerfile -t billing-agent:latest .
docker tag billing-agent:latest $ECR_URI
docker push $ECR_URI
```

### 2. Create config and secret

```bash
kubectl apply -f agents/billing/k8s/configmap.yaml
kubectl create secret generic billing-agent-keys -n support-agents \
  --from-literal=ANTHROPIC_API_KEY=sk-ant-your-key \
  --dry-run=client -o yaml | kubectl apply -f -
```

For Ollama or e2e: set `MOCK_LLM: "true"` in the ConfigMap. For Ollama, set `LLM_PROVIDER`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`.

### 3. Deploy

Edit `agents/billing/k8s/deployment.yaml` and set the image to your ECR URI. Then:

```bash
kubectl apply -f agents/billing/k8s/deployment.yaml
kubectl get pods -n support-agents -l app=billing-agent
kubectl logs -n support-agents -l app=billing-agent -f
```

### 4. E2E (full flow)

From repo root, with triage and billing both running and `MOCK_LLM=true` for both:

```bash
./scripts/e2e-specialists.sh
```

## Files

| File                 | Purpose                                           |
| -------------------- | ------------------------------------------------- |
| `configmap.yaml`     | Kafka bootstrap, LLM provider, `MOCK_LLM`, etc.   |
| `deployment.yaml`    | Deployment; update `image` before applying.       |
| `secret.yaml.example` | Example shape; create real secret with kubectl.  |
