output "kafka_bootstrap_servers" {
  description = "Bootstrap servers for Kafka (use in agent config as KAFKA_BOOTSTRAP_SERVERS). Resolves from pods/EC2 in the same VPC after running create-kafka-dns.sh in the Kafka platform repo."
  value       = "kafka.${var.kafka_dns_domain}:9092"
}

output "kafka_dns_zone_id" {
  description = "Route 53 private hosted zone ID (same as Kafka platform output; use when re-running create-kafka-dns.sh)."
  value       = data.aws_route53_zone.kafka_dns.zone_id
}

output "kafka_dns_zone_name" {
  description = "Kafka DNS domain name."
  value       = data.aws_route53_zone.kafka_dns.name
}

output "eks_cluster_endpoint" {
  description = "EKS API endpoint (for agent deployment or kubectl)."
  value       = data.aws_eks_cluster.this.endpoint
}

output "eks_cluster_name" {
  description = "EKS cluster name."
  value       = data.aws_eks_cluster.this.name
}
