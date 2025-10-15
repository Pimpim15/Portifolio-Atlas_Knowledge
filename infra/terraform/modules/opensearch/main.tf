variable "environment" { type = string }
variable "vpc_id" { type = string }
variable "private_subnet_ids" { type = list(string) }
variable "vpc_cidr_block" { type = string }
variable "instance_type" {
  type        = string
  default     = "t3.small.search"
  description = "Tipo de instância dos data nodes"
}
variable "instance_count" {
  type        = number
  default     = 2
  description = "Quantidade de instâncias no cluster"
}
variable "ebs_volume_size" {
  type        = number
  default     = 100
  description = "Tamanho (GiB) do volume EBS por nó"
}
variable "alarm_actions" {
  type        = list(string)
  description = "ARNs acionados quando alarmes disparam"
  default     = []
}

variable "ok_actions" {
  type        = list(string)
  description = "ARNs acionados quando alarmes normalizam"
  default     = []
}
variable "tags" {
  type        = map(string)
  description = "Tags adicionais para os recursos"
  default     = {}
}

locals {
  base_tags         = merge({ Environment = var.environment, Service = "atlas-knowledge", ManagedBy = "terraform" }, var.tags)
  subnet_candidates = length(var.private_subnet_ids) >= 2 ? slice(var.private_subnet_ids, 0, 2) : var.private_subnet_ids
}

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

resource "aws_security_group" "opensearch" {
  name        = "atlas-${var.environment}-os-sg"
  description = "Acesso interno para o OpenSearch"
  vpc_id      = var.vpc_id

  ingress {
    description = "Acesso HTTPS interno"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr_block]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.base_tags, { Name = "atlas-${var.environment}-os-sg" })
}

resource "aws_cloudwatch_log_group" "application" {
  name              = "/aws/opensearch/atlas-${var.environment}/application"
  retention_in_days = 30
  tags              = merge(local.base_tags, { Name = "atlas-${var.environment}-os-logs-application" })
}

resource "aws_cloudwatch_log_group" "index_slow" {
  name              = "/aws/opensearch/atlas-${var.environment}/index-slow"
  retention_in_days = 30
  tags              = merge(local.base_tags, { Name = "atlas-${var.environment}-os-logs-index-slow" })
}

resource "aws_cloudwatch_log_group" "search_slow" {
  name              = "/aws/opensearch/atlas-${var.environment}/search-slow"
  retention_in_days = 30
  tags              = merge(local.base_tags, { Name = "atlas-${var.environment}-os-logs-search-slow" })
}

resource "aws_opensearch_domain" "this" {
  domain_name    = "atlas-${var.environment}-os"
  engine_version = "OpenSearch_2.11"

  cluster_config {
    instance_type          = var.instance_type
    instance_count         = var.instance_count
    zone_awareness_enabled = var.instance_count >= 2 && length(local.subnet_candidates) >= 2

    dynamic "zone_awareness_config" {
      for_each = var.instance_count >= 2 && length(local.subnet_candidates) >= 2 ? [1] : []
      content {
        availability_zone_count = 2
      }
    }
  }

  vpc_options {
    security_group_ids = [aws_security_group.opensearch.id]
    subnet_ids         = local.subnet_candidates
  }

  ebs_options {
    ebs_enabled = true
    volume_size = var.ebs_volume_size
    volume_type = "gp3"
  }

  encrypt_at_rest {
    enabled = true
  }

  node_to_node_encryption {
    enabled = true
  }

  domain_endpoint_options {
    enforce_https       = true
    tls_security_policy = "Policy-Min-TLS-1-2-2019-07"
  }

  advanced_options = {
    "rest.action.multi.allow_explicit_index" = "true"
    "indices.fielddata.cache.size"           = "40"
  }

  log_publishing_options {
    cloudwatch_log_group_arn = aws_cloudwatch_log_group.application.arn
    log_type                 = "ES_APPLICATION_LOGS"
  }

  log_publishing_options {
    cloudwatch_log_group_arn = aws_cloudwatch_log_group.index_slow.arn
    log_type                 = "INDEX_SLOW_LOGS"
  }

  log_publishing_options {
    cloudwatch_log_group_arn = aws_cloudwatch_log_group.search_slow.arn
    log_type                 = "SEARCH_SLOW_LOGS"
  }

  access_policies = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "es:*"
        Resource = [aws_opensearch_domain.this.arn, "${aws_opensearch_domain.this.arn}/*"]
      }
    ]
  })

  tags = merge(local.base_tags, { Name = "atlas-${var.environment}-opensearch" })
}

output "endpoint" {
  value = aws_opensearch_domain.this.endpoint
}

output "security_group_id" {
  value = aws_security_group.opensearch.id
}

output "domain_arn" {
  value = aws_opensearch_domain.this.arn
}

resource "aws_cloudwatch_metric_alarm" "cluster_red" {
  alarm_name          = "atlas-${var.environment}-opensearch-cluster-red"
  namespace           = "AWS/ES"
  metric_name         = "ClusterStatus.red"
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_description   = "Cluster OpenSearch em estado RED"
  actions_enabled     = length(var.alarm_actions) > 0
  alarm_actions       = var.alarm_actions
  ok_actions          = var.ok_actions

  dimensions = {
    DomainName = aws_opensearch_domain.this.domain_name
    ClientId   = data.aws_caller_identity.current.account_id
  }

  tags = local.base_tags
}

resource "aws_cloudwatch_metric_alarm" "cluster_yellow" {
  alarm_name          = "atlas-${var.environment}-opensearch-cluster-yellow"
  namespace           = "AWS/ES"
  metric_name         = "ClusterStatus.yellow"
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 3
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_description   = "Cluster OpenSearch em estado YELLOW por 3 minutos"
  actions_enabled     = length(var.alarm_actions) > 0
  alarm_actions       = var.alarm_actions
  ok_actions          = var.ok_actions

  dimensions = {
    DomainName = aws_opensearch_domain.this.domain_name
    ClientId   = data.aws_caller_identity.current.account_id
  }

  tags = local.base_tags
}

resource "aws_cloudwatch_metric_alarm" "storage_low" {
  alarm_name          = "atlas-${var.environment}-opensearch-storage-low"
  namespace           = "AWS/ES"
  metric_name         = "FreeStorageSpace"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 1
  threshold           = 20480
  comparison_operator = "LessThanThreshold"
  treat_missing_data  = "breaching"
  alarm_description   = "Espaço livre em disco inferior a 20GiB"
  actions_enabled     = length(var.alarm_actions) > 0
  alarm_actions       = var.alarm_actions
  ok_actions          = var.ok_actions

  dimensions = {
    DomainName = aws_opensearch_domain.this.domain_name
    ClientId   = data.aws_caller_identity.current.account_id
  }

  tags = local.base_tags
}

resource "aws_cloudwatch_metric_alarm" "jvm_high" {
  alarm_name          = "atlas-${var.environment}-opensearch-jvm-high"
  namespace           = "AWS/ES"
  metric_name         = "JVMMemoryPressure"
  statistic           = "Average"
  period              = 300
  evaluation_periods  = 3
  threshold           = 85
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_description   = "Pressão JVM acima de 85% por 15 minutos"
  actions_enabled     = length(var.alarm_actions) > 0
  alarm_actions       = var.alarm_actions
  ok_actions          = var.ok_actions

  dimensions = {
    DomainName = aws_opensearch_domain.this.domain_name
    ClientId   = data.aws_caller_identity.current.account_id
  }

  tags = local.base_tags
}
