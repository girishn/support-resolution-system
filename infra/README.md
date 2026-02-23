# Support Resolution System – Infra

This directory looks up the **existing** EKS cluster and Kafka DNS zone created by [terraform-aws-confluent-platform](../terraform-aws-confluent-platform) and outputs values used by the support-resolution agents.

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

2. Apply:
   ```bash
   terraform init
   terraform apply
   ```

3. Use the outputs in your agent configuration:
   - `kafka_bootstrap_servers` → `KAFKA_BOOTSTRAP_SERVERS=kafka.confluent.local:9092`
   - `kafka_dns_zone_id` – when re-running the Kafka platform’s `create-kafka-dns.sh` script
