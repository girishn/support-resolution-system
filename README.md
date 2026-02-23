# Support Resolution System

AI agent–based customer support resolution: agents consume and produce Kafka events, use MCP for tools, and collaborate to triage, resolve, or escalate tickets.

## Repo layout

- **infra/** – Terraform that references the existing EKS + Kafka platform (from [terraform-aws-confluent-platform](https://github.com/your-org/terraform-aws-confluent-platform)) and outputs `kafka_bootstrap_servers`, `kafka_dns_zone_id`, etc. for agent config. See [infra/README.md](infra/README.md).
- **events/** – JSON Schema definitions for Kafka events: `ticket.created`, `ticket.triaged`. See [events/README.md](events/README.md).
- **agents/** – Agent services: **triage** (Phase 2) consumes `ticket.created`, produces `ticket.triaged`; Billing, Technical, Feature Guide (later).

## Prerequisites

1. Deploy the Kafka platform (terraform-aws-confluent-platform), apply Confluent manifests, and run the DNS script so `kafka.confluent.local` and broker hostnames resolve in the VPC.
2. Ensure agents run in the same VPC (e.g. on the same EKS cluster) or can reach Kafka bootstrap and brokers.

## Quick start (end-to-end)

Follow these commands in order for a minimal end-to-end run (EKS + Kafka + in-cluster Ollama + triage agent + e2e test).

### 1. Deploy Kafka platform (other repo)

In your **terraform-aws-confluent-platform** repo (not this one), deploy the EKS + Kafka cluster and DNS (see that repo’s README for details):

```bash
cd terraform-aws-confluent-platform/envs/dev
terraform init
terraform apply
```

This should give you an EKS cluster where `kafka.confluent.local:9092` and `b0`/`b1`/`b2` resolve inside the VPC.

### 2. Configure support-resolution-system infra (this repo)

From **support-resolution-system**:

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars: set cluster_name (same as Kafka cluster), region, kafka_dns_domain
terraform init
terraform apply
```

This wires this repo’s infra to the existing Kafka platform and outputs values like `kafka_bootstrap_servers`.

### 3. Create Kafka topic `ticket.events`

Still in **support-resolution-system**:

```bash
cd ..   # back to repo root if needed
./scripts/create-kafka-topics.sh
```

This creates `ticket.events` in the Kafka cluster (or leaves it as-is if it already exists).

### 4. Build and push triage agent image

From **support-resolution-system/agents/triage**:

```bash
cd agents/triage
docker build -t triage-agent:latest .

# Tag and push to your ECR (replace with your account/region):
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
ECR_URI="${ECR_REGISTRY}/triage-agent:latest"

aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "$ECR_REGISTRY"
aws ecr create-repository --repository-name triage-agent --region "$AWS_REGION" >/dev/null 2>&1 || true
docker tag triage-agent:latest "$ECR_URI"
docker push "$ECR_URI"
```

Edit `agents/triage/k8s/deployment.yaml` and set the image to `"$ECR_URI"` (or use the sed command in `agents/triage/k8s/README.md`).

### 5. Deploy namespace, config, Ollama, and triage agent

From **support-resolution-system** repo root:

```bash
kubectl apply -f agents/triage/k8s/namespace.yaml

# Non-sensitive config (Kafka bootstrap, topic, LLM provider, etc.)
kubectl apply -f agents/triage/k8s/configmap.yaml

# In-cluster Ollama (small qwen2.5:0.5b model, CPU-only, sized for t3.medium)
kubectl apply -f agents/triage/k8s/ollama.yaml

# Secret for LLM keys; for Ollama-only you can use a dummy value
kubectl create secret generic triage-agent-keys -n support-agents \
  --from-literal=ANTHROPIC_API_KEY=not-used \
  --dry-run=client -o yaml | kubectl apply -f -

# Deploy the triage agent
kubectl apply -f agents/triage/k8s/deployment.yaml

# Wait for pods
kubectl get pods -n support-agents
kubectl logs -n support-agents -l app=triage-agent -f
```

If the triage agent logs show `model 'qwen2.5:0.5b' not found`, pull it once on the Ollama pod:

```bash
kubectl exec -n support-agents deploy/ollama -- ollama pull qwen2.5:0.5b
```

### 6. Run the end-to-end test

From **support-resolution-system** repo root:

```bash
./scripts/e2e-triage.sh
```

You should see output like:

- `Triage ticket_id=e2e-...` and `Produced ticket.triaged...` in the triage agent logs.
- `PASS: Found ticket.triaged for ticket_id=...` from the e2e script.
