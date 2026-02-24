# DynamoDB table for customer enrichment, VPC endpoint (private access), and Pod Identity for the triage agent.
# Requires: EKS cluster with eks-pod-identity-agent addon (terraform-aws-confluent-platform provides this).

locals {
  vpc_id = data.aws_eks_cluster.this.vpc_config[0].vpc_id
}

# Route tables in the cluster's VPC (for DynamoDB Gateway endpoint)
data "aws_route_tables" "vpc" {
  vpc_id = local.vpc_id
}

# -----------------------------------------------------------------------------
# DynamoDB table for customer lookups
# -----------------------------------------------------------------------------

resource "aws_dynamodb_table" "customers" {
  name         = var.dynamodb_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "customer_id"

  attribute {
    name = "customer_id"
    type = "S"
  }

  tags = {
    Project     = "support-resolution-system"
    Environment = "dev"
  }
}

# -----------------------------------------------------------------------------
# DynamoDB Gateway VPC Endpoint (private access, no internet egress)
# -----------------------------------------------------------------------------

resource "aws_vpc_endpoint" "dynamodb" {
  vpc_id             = local.vpc_id
  service_name       = "com.amazonaws.${var.region}.dynamodb"
  vpc_endpoint_type  = "Gateway"
  route_table_ids    = data.aws_route_tables.vpc.ids

  tags = {
    Project     = "support-resolution-system"
    Environment = "dev"
  }
}

# -----------------------------------------------------------------------------
# IAM role for triage agent (Pod Identity)
# -----------------------------------------------------------------------------

resource "aws_iam_role" "triage_agent" {
  name = "${var.cluster_name}-triage-agent"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "AllowEksPodIdentityToAssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "pods.eks.amazonaws.com"
      }
      Action = [
        "sts:AssumeRole",
        "sts:TagSession"
      ]
    }]
  })
}

resource "aws_iam_role_policy" "triage_agent_dynamodb" {
  name   = "dynamodb-read"
  role   = aws_iam_role.triage_agent.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "dynamodb:GetItem",
        "dynamodb:BatchGetItem",
        "dynamodb:Query",
        "dynamodb:Scan"
      ]
      Resource = [
        aws_dynamodb_table.customers.arn,
        "${aws_dynamodb_table.customers.arn}/index/*"
      ]
    }]
  })
}

resource "aws_eks_pod_identity_association" "triage_agent" {
  cluster_name    = var.cluster_name
  namespace       = "support-agents"
  service_account = "triage-agent"
  role_arn        = aws_iam_role.triage_agent.arn
}
