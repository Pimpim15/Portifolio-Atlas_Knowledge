variable "environment" { type = string }
variable "vpc_id" { type = string }

resource "aws_opensearch_domain" "this" {
  domain_name           = "atlas-${var.environment}-os"
  engine_version        = "OpenSearch_2.9"
  cluster_config {
    instance_type = "t3.small.search"
    instance_count = 2
  }
  ebs_options {
    ebs_enabled = true
    volume_size = 20
  }
}

output "endpoint" {
  value = aws_opensearch_domain.this.endpoint
}
