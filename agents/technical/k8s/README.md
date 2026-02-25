# Technical Agent – Kubernetes

Deploy the Technical Agent to the same EKS cluster as Kafka and the Triage agent.

## Prerequisites

- Triage agent deployed and producing to `ticket.triaged.technical` (tickets classified as "technical")
- Kafka topics created (`scripts/create-kafka-topics.sh`)
- `kubectl` context set to the EKS cluster

**Optional:** Deploy Ollama in-cluster (see [triage k8s README](../../triage/k8s/README.md)) and set `LLM_PROVIDER=ollama` in the ConfigMap.

## Steps

### 1. Build and push the image

From **support-resolution-system** repo root:

```bash
export AWS_REGION=us-east-1
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/technical-agent:latest"

aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com
aws ecr create-repository --repository-name technical-agent --region $AWS_REGION 2>/dev/null || true

docker build -f agents/technical/Dockerfile -t technical-agent:latest .
docker tag technical-agent:latest $ECR_URI
docker push $ECR_URI
```

### 2. Create config and secret

```bash
kubectl apply -f agents/technical/k8s/configmap.yaml
kubectl create secret generic technical-agent-keys -n support-agents \
  --from-literal=ANTHROPIC_API_KEY=sk-ant-your-key \
  --dry-run=client -o yaml | kubectl apply -f -
```

For Ollama or e2e: set `MOCK_LLM: "true"` in the ConfigMap.

### 3. Deploy

Edit `agents/technical/k8s/deployment.yaml` and set the image to your ECR URI. Then:

```bash
kubectl apply -f agents/technical/k8s/deployment.yaml
kubectl get pods -n support-agents -l app=technical-agent
kubectl logs -n support-agents -l app=technical-agent -f
```

## Files

| File                 | Purpose                                           |
| -------------------- | ------------------------------------------------- |
| `configmap.yaml`     | Kafka bootstrap, LLM provider, `MOCK_LLM`, etc.   |
| `deployment.yaml`    | Deployment; update `image` before applying.       |
| `secret.yaml.example` | Example shape; create real secret with kubectl.  |
