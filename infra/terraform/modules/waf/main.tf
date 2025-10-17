variable "environment" { type = string }
variable "alb_arn" { type = string }
variable "rate_limit" {
  type        = number
  default     = 5000
  description = "Requests per 5 minutes before blocking"
}
variable "log_retention_days" {
  type        = number
  default     = 90
}

locals {
  base_tags = {
    Environment = var.environment
    Service     = "atlas-knowledge"
    ManagedBy   = "terraform"
  }
}

resource "aws_wafv2_web_acl" "this" {
  name  = "atlas-${var.environment}-waf"
  scope = "REGIONAL"

  default_action {
    allow {}
  }

  rule {
    name     = "AWS-AWSManagedRulesCommonRuleSet"
    priority = 1
    override_action { none {} }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "atlas-${var.environment}-waf-common"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "RateLimit"
    priority = 10
    action {
      block {}
    }
    statement {
      rate_based_statement {
        aggregate_key_type = "IP"
        limit              = var.rate_limit
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "atlas-${var.environment}-waf-rate"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "atlas-${var.environment}-waf"
    sampled_requests_enabled   = true
  }

  tags = merge(local.base_tags, { Name = "atlas-${var.environment}-waf" })
}

resource "aws_cloudwatch_log_group" "waf" {
  name              = "/aws/waf/atlas-${var.environment}"
  retention_in_days = var.log_retention_days
  tags              = merge(local.base_tags, { Name = "atlas-${var.environment}-waf-logs" })
}

resource "aws_wafv2_web_acl_logging_configuration" "this" {
  resource_arn = aws_wafv2_web_acl.this.arn
  log_destination_configs = [
    aws_cloudwatch_log_group.waf.arn
  ]

  redacted_fields {
    single_header { name = "authorization" }
  }
}

resource "aws_wafv2_web_acl_association" "alb" {
  resource_arn = var.alb_arn
  web_acl_arn  = aws_wafv2_web_acl.this.arn
}

output "web_acl_arn" {
  value = aws_wafv2_web_acl.this.arn
}
