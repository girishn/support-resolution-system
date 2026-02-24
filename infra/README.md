# Support Resolution System – Infra

This directory references the **existing** EKS cluster from [terraform-aws-confluent-platform](../terraform-aws-confluent-platform) and creates: DynamoDB table, VPC Gateway endpoint (private DynamoDB access), EKS Pod Identity for the triage agent, and Prometheus stack (Prometheus + Grafana + Alertmanager) for observability.

## Prerequisites

1. Deploy the Kafka platform first:
   ```bash
   cd ../terraform-aws-confluent-platform/envs/dev
   terraform init && terraform apply
   ```
2. Deploy Confluent (Zookeeper + Kafka) and run the DNS script so `kafka.confluent.local` and `b0/b1/b2.confluent.local` resolve (see Kafka platform README).

## Usage

1. Set variables (e.g. in `terraform.tfvars` or environment):
   - `cluster_name` – EKS cluster name (e.g. `confluent-dev-eks`)
   - `region` – AWS region
   - `kafka_dns_domain` – same as in the Kafka platform (default `confluent.local`)
   - `dynamodb_table_name` – optional, default `support-customers`
   - `prometheus_stack_chart_version` – optional, kube-prometheus-stack Helm chart version (default `67.3.0`)

2. Apply:
   ```bash
   terraform init
   terraform apply
   ```

3. Use the outputs in your agent configuration:
   - `kafka_bootstrap_servers` → `KAFKA_BOOTSTRAP_SERVERS=kafka.confluent.local:9092`
   - `dynamodb_table_name` → `DYNAMODB_TABLE` in triage agent ConfigMap (for customer enrichment)
   - `kafka_dns_zone_id` – when re-running the Kafka platform’s `create-kafka-dns.sh` script

4. **Prometheus stack** (optional): Deployed to `monitoring` namespace. Scrapes pods with `prometheus.io/scrape` annotations (including the triage agent). See [docs/observability.md](../docs/observability.md) for Grafana/Prometheus access.
