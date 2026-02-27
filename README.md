# Support Resolution System

AI agent–based customer support resolution: agents consume and produce Kafka events to triage, classify, and resolve tickets. **Triage** consumes `ticket.created`, classifies by type, and routes to type-specific topics; **Billing**, **Technical**, and **Feature** specialists consume from their topics and produce `ticket.resolved`.

## Repo layout

- **shared/** – Reusable libraries: `shared/topics.py` (topic mapping), `shared/specialist_base.py`, `shared/aws/dynamodb.py`.
- **agents/** – **triage** (consumes `ticket.events`, produces to `ticket.triaged.*`), **billing**, **technical**, **feature** (consume type-specific topics, produce `ticket.resolved`). Each has Dockerfile and k8s manifests.
- **events/** – JSON Schema for Kafka events. See [events/README.md](events/README.md).
- **infra/** – Terraform for DynamoDB, Prometheus stack, Pod Identity. See [infra/README.md](infra/README.md).
- **scripts/** – `create-kafka-topics.sh`, `e2e-triage.sh`, `e2e-specialists.sh`.
- **docs/observability.md** – Trace IDs, Prometheus metrics.

## Prerequisites

- **AWS CLI** configured with credentials
- **kubectl** and **Docker**
- **Terraform** 1.x
- Access to deploy to an AWS account

## Full deployment guide

### Option A – Single Python script (recommended)

Prerequisites: **terraform**, **aws CLI**, **kubectl**, **docker** on PATH. AWS credentials configured.

```bash
cd support-resolution-system

# Full provision: Kafka platform (from sibling repo) + infra + topics + agents
python scripts/provision.py --kafka-platform-path ../terraform-aws-confluent-platform --auto-approve

# Or if Kafka is already deployed:
python scripts/provision.py --cluster-name confluent-dev-eks --region us-east-1 --auto-approve
```

Use `--mock-llm` for E2E/CI (no LLM API calls). Use `--skip-*` to omit steps. Run `python scripts/provision.py --help` for options.

---

### Option B – Manual steps

Follow these steps in order. All commands assume you are in the indicated directory.

---

### Step 1: Deploy Kafka platform (terraform-aws-confluent-platform)

From the **terraform-aws-confluent-platform** repo (a separate repo):

```bash
cd terraform-aws-confluent-platform/envs/dev
cp terraform.tfvars.example terraform.tfvars   # if present
# Edit terraform.tfvars: set region, name (e.g. confluent-dev), cluster_version

terraform init
terraform apply
```

This creates VPC, EKS cluster, Confluent operator. Note the cluster name (e.g. `confluent-dev-eks`).

---

### Step 2: Apply Confluent Kafka manifests

Still in **terraform-aws-confluent-platform**:

```bash
# From repo root
cd ../..
aws eks update-kubeconfig --name confluent-dev-eks --region us-east-1   # use your cluster name and region

kubectl apply -k manifests/overlays/dev
kubectl wait --for=jsonpath='{.status.readyReplicas}'=3 statefulset/zookeeper -n confluent --timeout=300s
kubectl wait --for=jsonpath='{.status.readyReplicas}'=3 statefulset/kafka -n confluent --timeout=300s
```

---

### Step 3: Create Kafka DNS records (so kafka.confluent.local resolves)

From **terraform-aws-confluent-platform** repo root:

```bash
ZONE_ID=$(terraform -chdir=envs/dev output -raw kafka_dns_zone_id)
ZONE_ID=$ZONE_ID ./scripts/create-kafka-dns.sh
```

This creates CNAMEs for `kafka.confluent.local` and `b0/b1/b2.confluent.local` in the VPC private zone. If Kafka services don't have EXTERNAL-IP yet, wait and retry.

---

### Step 4: Configure support-resolution-system infra

From **support-resolution-system**:

```bash
cd support-resolution-system/infra
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars:
#   region       = "us-east-1"
#   cluster_name = "confluent-dev-eks"    # must match Kafka platform
#   kafka_dns_domain = "confluent.local"

terraform init
terraform apply
```

This creates DynamoDB table (optional enrichment), Prometheus stack, Pod Identity for triage. Use `cluster_name` from Step 1.

---

### Step 5: Create Kafka topics

From **support-resolution-system** repo root (kubectl context must be set to the EKS cluster):

```bash
cd ..
./scripts/create-kafka-topics.sh
```

Creates `ticket.events`, `ticket.triaged.billing`, `ticket.triaged.technical`, `ticket.triaged.feature_request`, `ticket.triaged.account`, `ticket.triaged.other`, `ticket.resolved`.

---

### Step 6: Build and push triage agent image

From **support-resolution-system** repo root (build context must include `shared/`):

```bash
export AWS_REGION=us-east-1
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
ECR_URI="${ECR_REGISTRY}/triage-agent:latest"

aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REGISTRY
aws ecr create-repository --repository-name triage-agent --region $AWS_REGION 2>/dev/null || true

docker build -f agents/triage/Dockerfile -t triage-agent:latest .
docker tag triage-agent:latest $ECR_URI
docker push $ECR_URI
```

**Windows (PowerShell):** Use `$env:AWS_REGION`, `$env:AWS_ACCOUNT_ID`, etc., and replace variable expansion with your values if needed.

---

### Step 7: Set triage agent image in deployment

Edit `agents/triage/k8s/deployment.yaml` and set `spec.template.spec.containers[0].image` to your ECR URI (e.g. `123456789012.dkr.ecr.us-east-1.amazonaws.com/triage-agent:latest`).

Or on Linux/macOS:
```bash
sed -i.bak "s|REPLACE_ME|$ECR_URI|g" agents/triage/k8s/deployment.yaml
# Or, if the file has a different placeholder:
sed -i.bak "s|940534692014.dkr.ecr.us-east-1.amazonaws.com/triage-agent:latest|$ECR_URI|g" agents/triage/k8s/deployment.yaml
```

---

### Step 8: Deploy namespace, config, Ollama, and triage agent

From **support-resolution-system** repo root:

```bash
kubectl apply -f agents/triage/k8s/namespace.yaml
kubectl apply -f agents/triage/k8s/serviceaccount.yaml
kubectl apply -f agents/triage/k8s/configmap.yaml

# In-cluster Ollama (CPU-only, qwen2.5:0.5b; no API key needed)
kubectl apply -f agents/triage/k8s/ollama.yaml

# Secret (use "not-used" for Ollama-only; replace with real key for Anthropic/OpenAI)
kubectl create secret generic triage-agent-keys -n support-agents \
  --from-literal=ANTHROPIC_API_KEY=not-used \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -f agents/triage/k8s/deployment.yaml
```

**For deterministic E2E (no LLM calls):** Edit `agents/triage/k8s/configmap.yaml`, set `MOCK_LLM: "true"`, then:
```bash
kubectl apply -f agents/triage/k8s/configmap.yaml
kubectl rollout restart deployment/triage-agent -n support-agents
```

---

### Step 9: Verify triage agent and Ollama

```bash
kubectl get pods -n support-agents
kubectl logs -n support-agents -l app=triage-agent -f
```

If logs show `model 'qwen2.5:0.5b' not found`, pull the model:

```bash
kubectl exec -n support-agents deploy/ollama -- ollama pull qwen2.5:0.5b
```

---

### Step 10: Run triage E2E test

From **support-resolution-system** repo root:

```bash
./scripts/e2e-triage.sh
```

Expected: `PASS: Found ticket.triaged for ticket_id=...` (with MOCK_LLM, triage classifies as billing, so output goes to `ticket.triaged.billing`).

---

### Step 11 (optional): Deploy specialist agents (billing, technical, feature)

For the full flow (triage → specialist → ticket.resolved), deploy the billing agent (and optionally technical, feature).

#### 11a. Build and push billing agent

From **support-resolution-system** repo root:

```bash
ECR_URI="${ECR_REGISTRY}/billing-agent:latest"   # re-use ECR_REGISTRY from Step 6
aws ecr create-repository --repository-name billing-agent --region $AWS_REGION 2>/dev/null || true

docker build -f agents/billing/Dockerfile -t billing-agent:latest .
docker tag billing-agent:latest $ECR_URI
docker push $ECR_URI
```

#### 11b. Edit billing deployment and config

Edit `agents/billing/k8s/deployment.yaml`: set `image` to your ECR URI (e.g. `123456789012.dkr.ecr.us-east-1.amazonaws.com/billing-agent:latest`).

For E2E: Edit `agents/billing/k8s/configmap.yaml`, set `MOCK_LLM: "true"`.

#### 11c. Deploy billing agent

```bash
kubectl apply -f agents/billing/k8s/configmap.yaml
kubectl create secret generic billing-agent-keys -n support-agents \
  --from-literal=ANTHROPIC_API_KEY=not-used \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f agents/billing/k8s/deployment.yaml

kubectl get pods -n support-agents -l app=billing-agent
kubectl logs -n support-agents -l app=billing-agent -f
```

#### 11d. Technical and feature agents (optional)

Repeat the same pattern for technical and feature. If starting a new shell, run `export AWS_REGION=us-east-1` and `export ECR_REGISTRY=$(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-east-1.amazonaws.com` first.

```bash
# Technical
aws ecr create-repository --repository-name technical-agent --region $AWS_REGION 2>/dev/null || true
docker build -f agents/technical/Dockerfile -t technical-agent:latest .
docker tag technical-agent:latest ${ECR_REGISTRY}/technical-agent:latest
docker push ${ECR_REGISTRY}/technical-agent:latest
# Edit agents/technical/k8s/deployment.yaml and configmap.yaml
kubectl apply -f agents/technical/k8s/configmap.yaml
kubectl create secret generic technical-agent-keys -n support-agents --from-literal=ANTHROPIC_API_KEY=not-used --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f agents/technical/k8s/deployment.yaml

# Feature
aws ecr create-repository --repository-name feature-agent --region $AWS_REGION 2>/dev/null || true
docker build -f agents/feature/Dockerfile -t feature-agent:latest .
docker tag feature-agent:latest ${ECR_REGISTRY}/feature-agent:latest
docker push ${ECR_REGISTRY}/feature-agent:latest
# Edit agents/feature/k8s/deployment.yaml and configmap.yaml
kubectl apply -f agents/feature/k8s/configmap.yaml
kubectl create secret generic feature-agent-keys -n support-agents --from-literal=ANTHROPIC_API_KEY=not-used --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f agents/feature/k8s/deployment.yaml
```

---

### Step 12: Run full-flow E2E test

From **support-resolution-system** repo root, with triage and billing both running and `MOCK_LLM=true` for both:

```bash
./scripts/e2e-specialists.sh
```

Expected: `PASS: Found ticket.resolved for ticket_id=...` with `resolved_by=billing`.

---

### Step 13 (optional): Python E2E

Requires Kafka and agents running (e.g. in k8s). From a machine that can reach Kafka (or from inside the cluster):

```bash
pip install -r tests/requirements.txt
KAFKA_BOOTSTRAP_SERVERS=kafka.confluent.local:9092 pytest tests/e2e/test_full_flow.py -v -s
```

---

## Layer 2: Integration tests

Integration tests verify components working together. Run unit tests (no external deps):

```bash
pip install -r tests/requirements.txt
pytest tests/unit/ -v
```

Run all tests (integration tests skip when services are unavailable):

```bash
pytest tests/ -v
```

| Test | What it verifies | Requirements |
|------|------------------|--------------|
| **Event schema** | `ticket.triaged` matches `events/ticket.triaged.schema.json` | None |
| **Agent + Kafka** | Agent consumes and produces real Kafka messages | `KAFKA_BOOTSTRAP_SERVERS` set, Kafka reachable |
| **Agent + DynamoDB** | Real DynamoDB call works with AWS credentials | `DYNAMODB_TABLE` + AWS creds, optional `DYNAMODB_TEST_CUSTOMER_ID` |
| **Agent + Ollama** | AI returns usable response in expected format | Ollama running, `MOCK_LLM` unset |

---

## Optional: DynamoDB enrichment

To enrich tickets with customer data, the triage agent needs `DYNAMODB_TABLE` and Pod Identity. Infra Terraform creates the table and role. After `terraform apply` in infra:

```bash
terraform -chdir=infra output -raw dynamodb_table_name
```

Set that value in `agents/triage/k8s/configmap.yaml` as `DYNAMODB_TABLE: "support-customers"` (or the output value), then apply and restart triage.

### Bootstrap test data

Seed the DynamoDB table with test customers for integration tests and E2E:

```bash
DYNAMODB_TABLE=$(terraform -chdir=infra output -raw dynamodb_table_name)
python scripts/seed-dynamodb.py --table "$DYNAMODB_TABLE"
```

Or use a custom JSON file: `python scripts/seed-dynamodb.py --table support-customers --file customers.json`

For integration tests, set `AUTO_SEED_DYNAMODB=1` to auto-seed before DynamoDB tests run.

---

## Optional: Prometheus and Grafana

The infra Terraform deploys kube-prometheus-stack to the `monitoring` namespace. Agent pods have `prometheus.io/scrape: "true"` annotations and are scraped automatically. See [docs/observability.md](docs/observability.md) for Grafana access.

---

## Troubleshooting

- **e2e-triage.sh fails: "No ticket.triaged"** – Check triage logs: `kubectl logs -n support-agents -l app=triage-agent --tail=150`. Ensure topics exist (`./scripts/create-kafka-topics.sh`). With MOCK_LLM, triage returns billing; e2e consumes from `ticket.triaged.billing`.
- **Ollama "model not found"** – Run `kubectl exec -n support-agents deploy/ollama -- ollama pull qwen2.5:0.5b`.
- **Kafka connection refused / UnknownHostException** – Ensure Step 3 (create-kafka-dns.sh) ran and Kafka services have EXTERNAL-IP. Agents must run in the same VPC (e.g. same EKS cluster).
- **Consumer offset past e2e message** – Scale triage to 0, reset offsets: `kafka-consumer-groups --bootstrap-server kafka.confluent.local:9092 --group triage-agent --topic ticket.events --reset-offsets --to-earliest --execute` (from a Kafka tools pod), then scale back to 1.

---

## Agent details

- [Triage agent](agents/triage/README.md) – Consumes `ticket.events`, produces to `ticket.triaged.*`
- [Billing agent](agents/billing/README.md) – Consumes `ticket.triaged.billing`, produces `ticket.resolved`
- [Technical agent](agents/technical/README.md) – Consumes `ticket.triaged.technical`, produces `ticket.resolved`
- [Feature agent](agents/feature/README.md) – Consumes `ticket.triaged.feature_request`, produces `ticket.resolved`
