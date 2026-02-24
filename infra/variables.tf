variable "region" {
  description = "AWS region (must match the region where the Kafka platform was deployed)."
  type        = string
  default     = "us-east-1"
}

variable "cluster_name" {
  description = "Name of the EKS cluster created by terraform-aws-confluent-platform (e.g. confluent-dev-eks)."
  type        = string
}

variable "kafka_dns_domain" {
  description = "Kafka private DNS domain (must match kafka_dns_domain in the Kafka platform and the domain in manifests/base/kafka.yaml)."
  type        = string
  default     = "confluent.local"
}

variable "dynamodb_table_name" {
  description = "Name of the DynamoDB table for customer enrichment (used by triage agent when DYNAMODB_TABLE is set)."
  type        = string
  default     = "support-customers"
}

variable "prometheus_stack_chart_version" {
  description = "Helm chart version for kube-prometheus-stack (Prometheus + Grafana + Alertmanager)."
  type        = string
  default     = "67.3.0"
}
