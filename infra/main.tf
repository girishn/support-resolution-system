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

# -----------------------------------------------------------------------------
# Kubernetes and Helm providers (for Prometheus stack)
# -----------------------------------------------------------------------------

provider "kubernetes" {
  host                   = data.aws_eks_cluster.this.endpoint
  cluster_ca_certificate = base64decode(data.aws_eks_cluster.this.certificate_authority[0].data)

  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args = [
      "eks",
      "get-token",
      "--cluster-name",
      data.aws_eks_cluster.this.name,
      "--region",
      var.region
    ]
  }
}

provider "helm" {
  kubernetes {
    host                   = data.aws_eks_cluster.this.endpoint
    cluster_ca_certificate = base64decode(data.aws_eks_cluster.this.certificate_authority[0].data)

    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args = [
        "eks",
        "get-token",
        "--cluster-name",
        data.aws_eks_cluster.this.name,
        "--region",
        var.region
      ]
    }
  }
}
