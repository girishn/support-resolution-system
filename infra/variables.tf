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
