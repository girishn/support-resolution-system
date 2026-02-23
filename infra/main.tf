# References the existing EKS cluster and Route 53 zone created by terraform-aws-confluent-platform.
# Run the Kafka platform Terraform first (in ../terraform-aws-confluent-platform/envs/dev), then apply this
# to get outputs for configuring the support-resolution agents.

data "aws_eks_cluster" "this" {
  name = var.cluster_name
}

data "aws_route53_zone" "kafka_dns" {
  name         = var.kafka_dns_domain
  private_zone = true
}
